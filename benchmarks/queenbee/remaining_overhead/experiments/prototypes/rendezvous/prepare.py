#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""Prepare isolated rendezvous variants from the frozen hybrid sources."""
from pathlib import Path
import difflib
import hashlib
import json

base=Path(__file__).resolve().parent
hybrid=base.parent/'hybrid'

def once(text,old,new):
    if text.count(old)!=1: raise ValueError('Unexpected anchor count: '+old[:90])
    return text.replace(old,new)

def transform(text):
    text=once(text,'// Isolated hybrid experiment: direct destinations with epoch-scoped pooled\n// ownership for early-message fallbacks and self copies.',
        '// Isolated rendezvous experiment: publish destinations before readiness,\n// then initiate eligible remote payloads only after matching peer readiness.')
    anchor='using Key = std::tuple<std::string, int, size_t>;\n'
    text=once(text,anchor,anchor+'''
// Readiness uses a distinct channel but the exact data-message sequence/tag.
// It contains no process-local pointers, and every receive publishes one token.
struct Readiness
{
    size_t bytes = 0;
    bool direct = false;

    template <typename Archive>
    void serialize(Archive & archive, unsigned int const)
    {
        archive & bytes & direct;
    }
};
''')
    text=once(text,'    size_t bytes_ = 0;\n    char * data_ = nullptr;',
        '    size_t bytes_ = 0;\n    bool requirePosted_ = false;\n    char * data_ = nullptr;')
    text=once(text,'            bool const copy)\n        : key_(std::move(key)), bytes_(bytes)',
        '            bool const copy, bool const requirePosted = false)\n        : key_(std::move(key)), bytes_(bytes), requirePosted_(requirePosted)')
    text=once(text,'                << bytes_ << allocator_;','                << bytes_ << requirePosted_ << allocator_;')
    text=once(text,'                >> bytes_ >> allocator_;','                >> bytes_ >> requirePosted_ >> allocator_;')
    text=once(text,'            target_ = claimTarget(key_, bytes_);\n',
        '''            target_ = claimTarget(key_, bytes_);
            if (requirePosted_ && !target_)
            {
                throw std::logic_error("rendezvous payload lost its posted target");
            }
''')
    text=once(text,'    collectives::channel_communicator channel;\n',
        '    collectives::channel_communicator channel;\n    collectives::channel_communicator readiness;\n')
    anchor='''        channel = collectives::create_channel_communicator(
            hpx::launch::sync, (basename + "/channel").c_str(),
            collectives::num_sites_arg(size),
            collectives::this_site_arg(rank));'''
    text=once(text,anchor,anchor+'''
        readiness = collectives::create_channel_communicator(
            hpx::launch::sync, (basename + "/readiness").c_str(),
            collectives::num_sites_arg(size),
            collectives::this_site_arg(rank));''')
    text=once(text,'                     size_t const sequenceTag)\n{\n    return Message',
        '                     size_t const sequenceTag,\n                     bool const requirePosted = false)\n{\n    return Message')
    text=once(text,'                   data, bytes, destination == group.rank);',
        '                   data, bytes, destination == group.rank, requirePosted);')
    anchor='''    size_t const sequenceTag = messageTag(group, destination, tag, true);
    collectives::set('''
    text=once(text,anchor,'''    size_t const sequenceTag = messageTag(group, destination, tag, true);
    // get installs a local continuation and returns an HPX future. Destroying
    // that future does not wait: eager standalone send behavior is preserved,
    // while the peer's eventual readiness token still has one consumer.
    auto const ready = collectives::get<transport::Readiness>(
        group.readiness, collectives::that_site_arg(destination),
        collectives::tag_arg(sequenceTag));
    (void) ready;
    collectives::set(''')
    anchor='''        source != group.rank);
    receiveBytes('''
    text=once(text,anchor,'''        source != group.rank);
    auto announced = collectives::set(
        group.readiness, collectives::that_site_arg(source),
        transport::Readiness{bytes, source != group.rank && bytes != 0},
        collectives::tag_arg(sequenceTag));
    receiveBytes(''')
    anchor='''            collectives::tag_arg(sequenceTag))
            .get());
}
catch (...)'''
    text=once(text,anchor,'''            collectives::tag_arg(sequenceTag))
            .get());
    // Channel set completes on storage/continuation delivery, not a peer wait.
    announced.get();
}
catch (...)''')
    anchor='''    // Publish before launching the outgoing action. An early incoming action
    // still falls back to owned storage rather than waiting for this entry.
    transport::Registration const posted(
        transport::Key{group.basename, source, receiveSequenceTag}, receiveData,
        receivedBytes, direct);
    auto sent = collectives::set(
        group.channel, collectives::that_site_arg(destination),
        messageBytes(group, destination, sendData, sendBytes, sendSequenceTag),
        collectives::tag_arg(sendSequenceTag));'''
    text=once(text,anchor,'''    // Publish before advertising readiness, and initiate that advertisement
    // before any wait. All-receive announcements break dependency cycles for
    // rings and mixed sendrecv/standalone/overlapping-buffer calls.
    transport::Registration const posted(
        transport::Key{group.basename, source, receiveSequenceTag}, receiveData,
        receivedBytes, direct);
    auto announced = collectives::set(
        group.readiness, collectives::that_site_arg(source),
        transport::Readiness{receivedBytes, direct && receivedBytes != 0},
        collectives::tag_arg(receiveSequenceTag));
    auto ready = collectives::get<transport::Readiness>(
        group.readiness, collectives::that_site_arg(destination),
        collectives::tag_arg(sendSequenceTag));
    bool requirePosted = false;
    if (direct)
    {
        auto const peer = ready.get();
        if (peer.bytes != sendBytes)
        {
            throw std::length_error("rendezvous receive byte count mismatch");
        }
        requirePosted = peer.direct;
    }
    // Self and overlap cases keep eager owned reception and finish the source
    // send before copying. Their readiness future is consumed without waiting.
    auto sent = collectives::set(
        group.channel, collectives::that_site_arg(destination),
        messageBytes(group, destination, sendData, sendBytes, sendSequenceTag,
                     requirePosted),
        collectives::tag_arg(sendSequenceTag));''')
    text=once(text,'    receiveBytes(receiveData, receivedBytes, incoming);\n',
        '    receiveBytes(receiveData, receivedBytes, incoming);\n    announced.get();\n')
    return text

record={'diagnostic_only':True,'built':False,'sources':{}}
for name in ('hpx-comm.cpp','hpx-comm-diagnostic.cpp'):
    old=(hybrid/name).read_text();new=transform(old)
    (base/name).write_text(new)
    (base/(name+'.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='hybrid/'+name,tofile='rendezvous/'+name)))
    record['sources'][name]={'base_sha256':hashlib.sha256(old.encode()).hexdigest(),'sha256':hashlib.sha256(new.encode()).hexdigest()}
for name in ('archive_helpers.hpp','receive-diagnostics.hpp'):
    (base/name).write_bytes((hybrid/name).read_bytes())
(base/'rendezvous_units.cpp').write_text((hybrid/'hybrid_units.cpp').read_text().replace('HYBRID_RECEIVE_UNITS','RENDEZVOUS_RECEIVE_UNITS'))
(base/'PROVENANCE.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
