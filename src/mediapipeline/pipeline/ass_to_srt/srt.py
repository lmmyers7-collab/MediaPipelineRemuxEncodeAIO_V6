from mediapipeline.pipeline.ass_to_srt.log import emit_prefixed
from mediapipeline.pipeline.ass_to_srt.timing import ms_to_srt


def _join_texts(a: str, b: str) -> str:
    """Join two cue texts, preserving order and dropping exact duplicates."""
    a_lines = a.split('\n') if a else []
    b_lines = b.split('\n') if b else []
    combined = list(a_lines)
    for ln in b_lines:
        if ln not in combined:
            combined.append(ln)
    return '\n'.join(combined)


def merge_overlapping_cues(
    cues: list[tuple[int, int, str]]
) -> list[tuple[int, int, str]]:
    """
    FIX#4: split-based overlap resolution.

    The old implementation was a GREEDY merge that extended the previous
    cue's end to max(pe, e). This caused dialogue lines to linger on
    screen for the entire duration of any sign-translation that briefly
    overlapped them: a dialogue at 10.0-12.0 s and a sign at 11.5-18.0 s
    would fuse into one cue "dialogue\\nsign" lasting 10.0-18.0 s. The
    dialogue was no longer connected to its actual timing.

    The new algorithm walks sorted cues and, for each pair (prev, curr)
    that overlap, emits up to three non-overlapping segments:

        [prev.start .. curr.start]                with prev.text
        [curr.start .. min(prev.end, curr.end)]   with prev.text + '\\n' + curr.text
        [min(prev.end, curr.end) .. max(prev.end, curr.end)]
                                                  with whichever text extends

    Zero-length segments are skipped. The result is sorted, non-
    overlapping, and temporally faithful to the source.

    Samsung's built-in SRT renderer and many DLNA clients only display
    one cue at a time; the combined middle segment is where the viewer
    sees dialogue+sign simultaneously without either being dropped.
    """
    filtered = sorted((c for c in cues if c[1] > c[0]),
                      key=lambda c: (c[0], c[1]))
    if not filtered:
        return []

    # Work off a mutable deque-like list so we can re-process when an
    # emitted tail segment overlaps with the NEXT source cue (rare but
    # possible with >2-way overlaps, e.g. dialogue + sign + lyrics all
    # layered during an opening sequence).
    pending = list(filtered)
    out: list[tuple[int, int, str]] = []

    def _insert_sorted(lst, item):
        """Insert item into lst preserving sort by (start, end)."""
        key = (item[0], item[1])
        lo, hi = 0, len(lst)
        while lo < hi:
            mid = (lo + hi) // 2
            k = (lst[mid][0], lst[mid][1])
            if k < key:
                lo = mid + 1
            else:
                hi = mid
        lst.insert(lo, item)

    while pending:
        curr = pending.pop(0)
        if not out:
            out.append(curr)
            continue
        ps, pe, pt = out[-1]
        cs, ce, ct = curr

        if cs >= pe:
            # No overlap.
            out.append(curr)
            continue

        # Overlap. Remove the previous emitted segment; we'll rebuild
        # from it plus curr.
        out.pop()

        # Segment A: [ps, cs] with prev text (only if non-zero).
        if cs > ps:
            out.append((ps, cs, pt))

        # Segment B: [cs, min(pe, ce)] with combined text.
        mid_end = min(pe, ce)
        if mid_end > cs:
            out.append((cs, mid_end, _join_texts(pt, ct)))

        # Segment C: [min(pe, ce), max(pe, ce)] with whichever outlives.
        if pe > ce:
            tail = (mid_end, pe, pt)
        elif ce > pe:
            tail = (mid_end, ce, ct)
        else:
            tail = None

        if tail and tail[1] > tail[0]:
            # Push tail back into pending in sort order so it participates
            # correctly in any further overlap resolution with the next
            # source cue (which may start earlier than the tail).
            _insert_sorted(pending, tail)

    return out


def apply_minimum_gap(
    cues: list[tuple[int, int, str]],
    gap_ms: int = 1,
) -> list[tuple[int, int, str]]:
    """
    FIX#15: ensure every cue ends at least `gap_ms` ms before the next
    cue starts.

    Old behaviour: when shortening prev.end by gap_ms would push it
    below or onto prev.start, the fix was skipped and the zero-gap
    pair survived into the SRT: VLC still dropped the second cue.

    New behaviour: two-pass.
        Pass 1 (preferred): shorten current's end by gap_ms if
        feasible (current.start + 1 <= new_end).
        Pass 2 (fallback):  shift NEXT cue's start forward by gap_ms
        when the current cue cannot be shortened. We only do this if
        the next cue is long enough to absorb the shift without
        inverting: if both cues are 1 ms wide with zero gap, we log
        and leave them alone (pathological input).

    A 1 ms gap is imperceptible at any frame rate but unambiguously
    distinguishes two adjacent cues.

    Input:  list of (start_ms, end_ms, text), sorted by start.
    Output: list of (start_ms, end_ms, text) with end_i < start_{i+1}.
    """
    if len(cues) < 2:
        return cues
    out = [list(c) for c in cues]
    fallback_count = 0
    unresolved     = 0

    for i in range(len(out) - 1):
        cur_end    = out[i][1]
        next_start = out[i + 1][0]
        if cur_end < next_start:
            continue  # already has a gap

        new_end = next_start - gap_ms
        if new_end > out[i][0]:
            # Pass 1: shorten current's end.
            out[i][1] = new_end
            continue

        # Pass 2 fallback: advance next.start by gap_ms if possible.
        desired_next_start = cur_end + gap_ms
        if desired_next_start < out[i + 1][1]:
            out[i + 1][0] = desired_next_start
            fallback_count += 1
            continue

        # Pathological: adjacent cues have zero or negative width and
        # we can't introduce a gap without inverting one of them.
        # Leave them alone: dropping either would lose dialogue.
        unresolved += 1

    if fallback_count:
        emit_prefixed(f"INFO: apply_minimum_gap fallback (shifted next.start) "
                      f"applied to {fallback_count} cue pair(s)")
    if unresolved:
        emit_prefixed(f"WARN: apply_minimum_gap could not resolve {unresolved} "
                      f"zero-width pair(s); leaving as-is")

    return [tuple(c) for c in out]


def render_srt(cues: list[tuple[int, int, str]]) -> str:
    output_lines = []
    for i, (s, e, t) in enumerate(cues, start=1):
        output_lines.append(str(i))
        output_lines.append(f"{ms_to_srt(s)} --> {ms_to_srt(e)}")
        output_lines.append(t)
        output_lines.append("")
    return "\n".join(output_lines)
