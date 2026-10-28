import os
import time

from lecture_study.scanner import HashIndex, find_stable_recordings, sha256_file


def make(path, content=b"audio", age=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    moment = time.time() - age
    os.utime(path, (moment, moment))
    return path


def test_finds_stable_audio_in_subfolders_oldest_first(tmp_path):
    older = make(tmp_path / "corso" / "a.M4A", age=600)
    newer = make(tmp_path / "b.mp3", age=120)
    make(tmp_path / "note.txt")
    make(tmp_path / "in-copia.wav", age=5)
    found = find_stable_recordings(tmp_path, stable_seconds=30, now=time.time())
    assert [recording.path for recording in found] == [older, newer]


def test_sha256_of_known_content(tmp_path):
    path = make(tmp_path / "a.wav", b"abc")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_hash_index_reuses_digest_until_file_changes(tmp_path):
    path = make(tmp_path / "a.wav", b"uno")
    calls = []

    def hasher(target):
        calls.append(target)
        return sha256_file(target)

    recording = find_stable_recordings(tmp_path, stable_seconds=0, now=time.time())[0]
    index = HashIndex(tmp_path / "index.json", hasher=hasher)
    first = index.hash_of(recording)
    index.save()

    reloaded = HashIndex(tmp_path / "index.json", hasher=hasher)
    assert reloaded.hash_of(recording) == first
    assert len(calls) == 1

    make(path, b"due", age=30)
    changed = find_stable_recordings(tmp_path, stable_seconds=0, now=time.time())[0]
    assert reloaded.hash_of(changed) != first
    assert len(calls) == 2
