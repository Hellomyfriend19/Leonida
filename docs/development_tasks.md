# Development tasks

Priority order for this workspace. Existing working code stays. A task is done when the subsystem
is tested on its own, not when it compiles.

Hard boundary, already measured in [rpf.md](rpf.md): the RPF9 table of contents is encrypted. This
list does not include decrypting it, searching for keys, or inventing original paths the TOC would
have held. Names that exist are the ones recovered from payload text
([resource_names.md](resource_names.md) and the name-recovery census in [rpf.md](rpf.md): 177,087 of
1,489,677 streams, 11.89%). The rest stay offset-addressed.

`tools/rpf9_carve.py --index-only` and `tools/rpf9_names.py` already walk the data area without
writing inflated files. `runtime/shims/file_system.cpp` and `runtime/shims/dstorage.cpp` still open
loose files under `GAME:`. The gap is a reader that serves one stream from the archive when the
runtime asks for it.

## 1. On-demand RPF filesystem

Success: a caller can open a supported RPF9, look up a stream, and read its bytes without an
extracted copy of the archive. Supported means what [rpf.md](rpf.md) already reads: header, zlib
streams, Bink 2 where the walker accepts it, raw AWC in `audio.rpf`. Unread ranges stay unread.

1. **Write the read contract.** One request is an archive plus a stream key. Keys, in order of
   what we can resolve today: stored offset, a payload name from the names index, a joaat or
   64-bit hash when a measured table already uses one. A path that exists only in the TOC is a
   miss, recorded as such.
2. **Persist the stream index.** Reuse the `--index-only` record (`off`, `stored`, `size`, `head`,
   unread ranges, trailer). The index is local scratch, not repository content. It is the directory
   the encrypted TOC does not give us.
3. **Read one stream.** Open the archive, seek to `off`, inflate that zlib stream (or copy a raw
   span the walker already classifies), return the bytes. Do not scan or write the rest of the
   archive.
4. **Bound memory.** A stream larger than a configured limit is read in inflate windows and can be
   streamed to the caller. Do not require the inflated resource to reside fully in RAM before the
   first byte is returned when the caller only needs a prefix.
5. **State the random-access limit.** Deflate is sequential inside one stream. Random access is
   choosing a stream, then reading forward inside it. A byte range in the middle of a stream
   inflates from the start of that stream up to the range, then caches the result. Do not claim
   block-level seeks inside a zlib stream.
6. **Cache.** LRU of inflated streams with a byte cap, keyed by archive plus offset. A second read
   of the same stream does not inflate again. Eviction is explicit and testable.
7. **Concurrent readers.** Several reads of different streams in one archive at once. One read does
   not move another reader's file position. Document whether the archive mapping is shared.
8. **Virtual files.** `GAME:` lookup checks a loose file first (current overlay and package
   behaviour in `file_system.cpp`). On a miss, resolve through the stream index and serve a read
   handle. Directory listing returns only names the index actually has.
9. **DirectStorage path.** `IDStorageFactoryX::OpenFile` already goes through `CreateFileW`. Once
   step 8 answers those opens, a queue request can read a stream that was never extracted. Zlib
   requests the shim already inflates stay as they are when the source is still compressed.
10. **Tests without the package.** Synthetic archives in the style of `tests/test_rpf9_carve.py`:
    index, lookup hit and miss, single-stream inflate, prefix read, cache hit, two concurrent
    reads, and a hash match between the on-demand bytes and a one-stream carve of the same
    fixture. A local package run, if you have one, compares hashes and records peak RAM. It does
    not commit archives, indexes, or inflated bytes.

## 2. Xbox D3D12 to Vulkan

The layer already exists under `runtime/shims/d3d12_*` and `runtime/src/vulkan_*`. Status is
[d3d12_vulkan.md](d3d12_vulkan.md). Do not replace it.

1. List which device, queue, command-list, barrier, copy, and present calls the current shims
   implement, and which boot stops in [retail_boot_chain.md](retail_boot_chain.md) are still open.
2. Close the next unimplemented call the retail boot actually hits, one call at a time, with the
   reason recorded before the change.
3. Keep a GPU check for each new translation: a small runtime test that submits the call and
   checks the result on a real device. `spirv-val` alone does not close the task.
4. Leave unsupported calls logged and failed. No silent success.

## 3. Shader translation on a real GPU

The translator and its contract live in `tools/rdna2spirv.py` and [design.md](design.md). A new
rule is a fixture under `tests/semantic/` plus a contract-table row.

1. Keep the semantic suite green on one fixture while iterating, then the full
   `scripts/run_semantic_tests.py` run before a change is called done.
2. For a rule that changes lowering, run `scripts/run_gpu_tests.py` on the installed GPU and
   record the device and driver next to the result.
3. Cache compiled pipelines so a repeated boot does not recompile the same shader. Measure
   compile time before and after on the same GPU.

## 4. Executable and system compatibility

Loader, import shims, and the x64 host path are already in `runtime/`. The retail executable is
not in this repository.

1. From [boot.md](boot.md) and [retail_boot_chain.md](retail_boot_chain.md), name the next stop
   `gta6rt --run` hits and the import or service that stop needs.
2. Implement that import in the existing shim style. A controlled executable or the retail boot
   log must show the stop has moved.
3. Connect filesystem opens from step 1.8 before treating a missing asset as a loader bug.

## 5. First rendered frame

Only after 1–4 have a measured stop to push.

1. Load the executable, map `GAME:`, and bring up the device with the current shims.
2. Log each failed import, missing stream, and rejected D3D12 call in order.
3. Fix the first failure that is in scope. Repeat. A frame is the success criterion: the retail
   title presents once on the Windows host. Playable gameplay, audio, and performance are later
   work and are not part of this criterion.

## Throughout

| Work | When |
|---|---|
| Log the failing call, path, and HRESULT | Any boot or reader failure |
| Synthetic tests, no game bytes in the tree | Every new reader or translator rule |
| Note the decision and the file it lives in | Any change to the read contract or an ABI guess |
| GPU run on the machine that has the device | Any shader or Vulkan change called done |
