#!/usr/bin/env python3
"""Extract one save directory from a raw 8 MB PS2 memory-card image."""

from pathlib import Path
import argparse
import struct


class CardError(RuntimeError):
    pass


def extract_save(card: Path, save_name: str, output: Path):
    raw = card.read_bytes()
    if raw[:28] != b"Sony PS2 Memory Card Format ":
        raise CardError("not a PS2 memory-card image")
    page_len, pages_per_cluster, pages_per_block = struct.unpack_from("<HHH", raw, 0x28)
    clusters_per_card, alloc_offset, alloc_end, root_cluster = struct.unpack_from("<IIII", raw, 0x30)
    if page_len != 512 or pages_per_cluster != 2 or pages_per_block != 16:
        raise CardError("unsupported memory-card geometry")
    raw_page = len(raw) // (clusters_per_card * pages_per_cluster)
    if raw_page < page_len or len(raw) % (clusters_per_card * pages_per_cluster):
        raise CardError("invalid memory-card size")
    cluster_size = page_len * pages_per_cluster

    def physical_cluster(number):
        if not 0 <= number < clusters_per_card:
            raise CardError(f"physical cluster out of range: {number}")
        pieces = []
        for page_index in range(pages_per_cluster):
            start = (number * pages_per_cluster + page_index) * raw_page
            pieces.append(raw[start:start + page_len])
        return b"".join(pieces)

    # The superblock's indirect-FAT list starts at 0x50.  Each indirect
    # cluster names the physical FAT clusters; FAT indices are allocation-area
    # relative cluster numbers.
    ifc_list = struct.unpack_from("<32I", raw, 0x50)
    fat_cluster_count = (alloc_end - alloc_offset + cluster_size // 4 - 1) // (cluster_size // 4)
    fat_clusters = []
    for ifc_number in ifc_list:
        if ifc_number == 0xFFFFFFFF:
            break
        fat_clusters.extend(struct.unpack(f"<{cluster_size // 4}I", physical_cluster(ifc_number)))
        if len(fat_clusters) >= fat_cluster_count:
            break
    fat_numbers = fat_clusters[:fat_cluster_count]
    if len(fat_numbers) != fat_cluster_count:
        raise CardError("incomplete indirect FAT")
    fat = []
    for number in fat_numbers:
        fat.extend(struct.unpack(f"<{cluster_size // 4}I", physical_cluster(number)))

    def chain(start):
        result = []
        current = start
        while True:
            if current in result or not 0 <= current < len(fat):
                raise CardError(f"broken FAT chain at {current}")
            result.append(current)
            value = fat[current]
            if value == 0xFFFFFFFF:
                return result
            if not value & 0x80000000:
                raise CardError(f"free cluster inside FAT chain at {current}")
            current = value & 0x7FFFFFFF

    def allocation_cluster(relative):
        return physical_cluster(alloc_offset + relative)

    def entries(directory_cluster, count):
        found = []
        for relative in chain(directory_cluster):
            data = allocation_cluster(relative)
            for pos in range(0, cluster_size, 512):
                mode, _, length = struct.unpack_from("<HHI", data, pos)
                first_cluster, = struct.unpack_from("<I", data, pos + 0x10)
                name = data[pos + 0x40:pos + 0x60].split(b"\0", 1)[0].decode("ascii", "replace")
                if mode != 0xFFFF:
                    found.append((mode, length, first_cluster, name))
                if len(found) >= count:
                    return found
        return found

    root_entries = entries(root_cluster, struct.unpack_from("<I", allocation_cluster(root_cluster), 4)[0])
    wanted = next((e for e in root_entries if e[3] == save_name and e[0] & 0x20), None)
    if wanted is None:
        raise CardError(f"save directory not found: {save_name}")
    directory_entries = entries(wanted[2], wanted[1])

    output.mkdir(parents=True, exist_ok=True)
    written = []
    for mode, size, first_cluster, name in directory_entries:
        if name in (".", "..") or mode & 0x20 or not name:
            continue
        if any(ch in name for ch in "\\/:"):
            raise CardError(f"unsafe file name: {name!r}")
        content = bytearray()
        for relative in chain(first_cluster):
            content.extend(allocation_cluster(relative))
            if len(content) >= size:
                break
        if len(content) < size:
            raise CardError(f"file is incomplete: {name}")
        target = output / name
        target.write_bytes(content[:size])
        written.append((name, size))

    if not written:
        raise CardError("the save directory contains no files")
    for name, size in written:
        print(f"{name}\t{size}")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("card", type=Path)
    ap.add_argument("save_name")
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
    extract_save(args.card, args.save_name, args.output)


if __name__ == "__main__":
    main()
