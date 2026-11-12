"""Interview explainers for Easy programs.

`python3 -m easy --interview FILE` prints a plain-words answer you can give
in an interview: what the program does, the key steps, the time and space
cost, and what to watch for.

Explainers are looked up from a catalog of the examples in this repository
(and of the session listings in the data-structures book). A program may
also carry its own explainer in comments that start with `¤ Interview:`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class InterviewError(Exception):
    """The program has no interview explainer."""


@dataclass(frozen=True)
class Explainer:
    """One algorithm, ready to say out loud."""

    id: str
    title: str
    does: str
    steps: str
    cost: str
    watch: str
    filenames: frozenset[str] = field(default_factory=frozenset)
    procedures: frozenset[str] = field(default_factory=frozenset)
    markers: frozenset[str] = field(default_factory=frozenset)


def _explainer(id, title, does, steps, cost, watch, filenames=(), procedures=(), markers=()):
    return Explainer(
        id=id,
        title=title,
        does=does,
        steps=steps,
        cost=cost,
        watch=watch,
        filenames=frozenset(filenames),
        procedures=frozenset(procedures),
        markers=frozenset(markers),
    )


# Catalog. `procedures` is the set that must all appear in the source
# (MAIN is ignored). More specific sets win over subsets.
CATALOG: list[Explainer] = [
    _explainer(
        "nodes",
        "A singly linked list",
        "A singly linked list is a chain of nodes, each holding a value and a link to the next node, ending at nil.",
        "I allocate each node, fill its value, and hook it to the next so I can walk from the first node to the last.",
        "Building or walking n nodes takes O(n) time and O(n) space. Inserting at the front is O(1).",
        "The walk must stop at nil, or it never ends. I'd use a linked list when the length will change, or when I often add at the front.",
        filenames=("nodes", "links"),
        procedures=(),
    ),
    _explainer(
        "euclid",
        "Euclid's algorithm",
        "Euclid's algorithm finds the greatest common divisor by replacing the pair (a, b) with (b, a mod b) until the remainder is 0. The last non-zero remainder is the GCD.",
        "While b is not 0, I store a mod b, move b into a, and move the remainder into b. Then I return a.",
        "Each remainder is strictly smaller than the last, so the loop takes O(log n) steps and O(1) extra space.",
        "If b starts at 0, the answer is a at once. Languages disagree about remainders of negative numbers, so I'd mention that if the inputs might not be positive.",
        filenames=("euclid", "gcd"),
        procedures=("GCD",),
    ),
    _explainer(
        "horner",
        "Horner's rule",
        "Horner's rule evaluates a polynomial by folding from the highest coefficient: at each step I multiply the accumulator by x and add the next coefficient.",
        "Start the accumulator at 0, then for each coefficient from high to low do acc ← acc × x + coefficient, and return acc.",
        "n terms take O(n) time and O(1) extra space, instead of computing each power of x on its own.",
        "I'd use it whenever I need to evaluate a polynomial quickly. A missing or reordered coefficient will silently give the wrong value.",
        filenames=("horner",),
        procedures=("Horner",),
    ),
    _explainer(
        "factorial",
        "A recursive factorial",
        "The factorial of n is n times the factorial of n - 1, and the factorial of 0 is 1, so the procedure calls itself until it hits that base case.",
        "If n is 0 I return 1; otherwise I return n times Fact(n - 1).",
        "There are n calls, and each one waits on the stack, so the time and the stack space are both O(n).",
        "A large n can overflow the call stack; an ordinary loop would use O(1) extra space. I'd use the recursive form to explain the idea, and a loop if I only needed the number.",
        filenames=("factorial",),
        procedures=("Fact",),
    ),
    _explainer(
        "insertion",
        "Insertion sort",
        "Insertion sort keeps a growing sorted prefix. I lift each next value, shift larger neighbors one cell right, and drop it into the gap.",
        "For each index i from 2 to n I hold a(i), slide every larger neighbor to the right, and write the held value into the gap.",
        "In the worst case every insert slides across the whole prefix, so the time is O(n^2); already-sorted input is O(n). It works in place, using O(1) extra space.",
        "If the inner test is 'greater than', not 'greater or equal', equal items keep their original order and the sort is stable. I'd use it for a short list, or one that is already nearly sorted.",
        filenames=("insertion",),
        procedures=("Sort",),
    ),
    _explainer(
        "linear",
        "Linear search",
        "Linear search walks the table from the first cell until it finds the key or runs out of cells.",
        "I start at index 1 and compare each cell to the key. If I find it I return the index; if I reach the end I return 0.",
        "A missing key looks at every cell, so the worst case is O(n), and the extra space is O(1). The table need not be sorted.",
        "If I already know which keys are asked for most often, I'd put those near the front. I'd use this on a short table, or one I cannot keep in order.",
        filenames=(),
        procedures=("Linear",),
    ),
    _explainer(
        "binary",
        "Binary search",
        "Binary search finds a key in a sorted table by looking at the middle of the remaining range and throwing away the half that cannot hold the key.",
        "I keep two ends, lo and hi. Each step I look at the middle: if that cell is the key I return its index; if the key is larger I search the right half; otherwise I search the left. If the range is empty I return 0, meaning the key is absent.",
        "The range halves each step, so the time is O(log n) and the extra space is O(1).",
        "The table must already be sorted, or the answer can be wrong. I'd use this on a static sorted table, and I'd be careful with the middle index on a very large range.",
        filenames=(),
        procedures=("Binary",),
    ),
    _explainer(
        "find-binary",
        "Binary search",
        "Binary search finds a key in a sorted table by looking at the middle of the remaining range and throwing away the half that cannot hold the key.",
        "I keep two ends, lo and hi. Each step I look at the middle: if that cell is the key I return its index; if the key is larger I search the right half; otherwise I search the left. If the range is empty I return 0, meaning the key is absent.",
        "The range halves each step, so the time is O(log n) and the extra space is O(1).",
        "The table must already be sorted, or the answer can be wrong. I'd use this on a static sorted table, and I'd be careful with the middle index on a very large range.",
        filenames=(),
        procedures=("Find",),
        markers=("mid",),
    ),
    _explainer(
        "hanoi",
        "The Towers of Hanoi",
        "To move a tower of n disks, I move n - 1 disks to the spare peg, move the largest disk to the destination, then move the n - 1 disks on top of it.",
        "The one-disk case is the base: just move that disk. Otherwise I recurse to the spare, move the largest disk, and recurse again onto the destination.",
        "The number of moves is 2^n - 1, so the time is O(2^n) and the call stack is O(n) deep.",
        "It grows too fast for a large n. I'd use it to explain recursion, not as a practical routine for a tall tower.",
        filenames=("hanoi",),
        procedures=("Move",),
    ),
    _explainer(
        "stack",
        "An array stack",
        "A stack is last in, first out: you only add and remove at the top.",
        "To push, I check that the array is not full, then raise top and write in that cell. To pop, I check that it is not empty, read the top cell, and lower top.",
        "Each of those steps is O(1), and the array uses O(n) space for a pile of capacity n.",
        "The two mistakes to name are overflow (pushing when it is full) and underflow (popping when it is empty). I'd use an array stack when I know a safe bound on the size.",
        filenames=("stack", "pile"),
        procedures=("Init", "Push", "Pop"),
    ),
    _explainer(
        "linked-stack",
        "A linked stack",
        "A linked stack stores the top as a pointer to the first node, and each node points to the one beneath it.",
        "To push, I make a new node, point it at the old top, and only then move top to the new node. To pop, I read the top node, advance top to its link, and return the node to the pool.",
        "Push and pop are O(1), and n items use O(n) space. There is no fixed capacity, so the stack grows until memory runs out.",
        "The order of the two assignments in a push matters: if I move top first, I lose the rest of the chain. I'd use this form when I don't know a bound on the size.",
        filenames=("linked_pile",),
        procedures=("Push", "Pop"),
        markers=("GETNODE",),
    ),
    _explainer(
        "brackets",
        "Matching brackets",
        "To check brackets, I push each opener and, when I see a closer, I pop and demand that it match. Last in, first out is exactly the nesting rule.",
        "I scan the string once. An opener goes on the stack. A closer must match the current top; if the stack is empty, or the pair does not match, the string is not balanced. At the end the stack must be empty.",
        "The time is O(n) and the extra space is O(n) in the worst case, when every character is an opener.",
        "Leftover openers, a closer with no opener, and a mismatched pair are the three ways it fails. I'd use this for any nested delimiters.",
        filenames=("brackets",),
        procedures=("Balanced",),
    ),
    _explainer(
        "ring",
        "A circular queue",
        "A circular queue is a FIFO ring in a fixed array. I add at the back and take from the front, and the indexes wrap around with mod.",
        "Enqueue writes in the cell just after the last item and raises the count. Dequeue reads the front cell, advances front, and lowers the count. A separate count tells a full ring from an empty one.",
        "Enqueue and dequeue are both O(1), and the array uses O(n) space for a ring of capacity n.",
        "The two mistakes are enqueue on a full ring and dequeue on an empty one. I'd use this for a buffer whose length has a known bound.",
        filenames=("ring",),
        procedures=("Enqueue", "Dequeue"),
        markers=("mod n",),
    ),
    _explainer(
        "linked-queue",
        "A linked queue",
        "A linked queue keeps a pointer to the front and a pointer to the rear, so I can add at the back and take from the front in O(1) time.",
        "Enqueue hangs a new node after the tail, or sets both head and tail if the queue was empty. Dequeue unlinks the head and, if the queue is now empty, clears the tail as well, so the rear never dangles.",
        "n items use O(n) space, and there is no fixed capacity.",
        "Forgetting to clear the tail when the last node leaves is the usual bug: the next enqueue would attach to a node that is no longer in the queue. I'd use this when the length of the line is not known in advance.",
        filenames=("linked_queue",),
        procedures=("Enqueue", "Dequeue"),
        markers=("GETNODE",),
    ),
    _explainer(
        "preorder",
        "A preorder walk",
        "Preorder visits a node, then its left subtree, then its right subtree. I write the node first, then recurse on each child.",
        "If the node is nil I return at once. Otherwise I record its value, walk the left child, and walk the right child.",
        "Every node is visited once, so the time is O(n). The call stack is as deep as the height, which is O(n) in the worst case if the tree is a single chain.",
        "I'd use preorder when I need to see a node before I see the work hanging under it.",
        filenames=(),
        procedures=("Pre",),
    ),
    _explainer(
        "bst",
        "Binary search tree insert",
        "In a binary search tree, every left descendant is smaller than the node and every right descendant is larger. To insert, I walk left or right until I find an empty link, and I hang a new leaf there.",
        "If the root is empty I create a leaf and store it there. If the new key is smaller I insert into the left child; otherwise I insert into the right child.",
        "A search or an insert follows one path, so the time is O(h). If keys arrive in random order, h is about log n on average; if they arrive already sorted, the tree becomes a chain and the time is O(n). The tree uses O(n) space, and the recursion uses O(h) stack space.",
        "I'd use a plain BST when I need ordered search with inserts, and I'd switch to a balanced tree if the arrival order might be sorted.",
        filenames=("bst",),
        procedures=("Insert",),
    ),
    _explainer(
        "height",
        "The height of a tree",
        "The height of a node is one plus the taller of its two subtrees, and the height of an empty tree is 0, so a leaf has height 1.",
        "I ask each child for its height and return the larger one, plus one.",
        "That walks every node once, in O(n) time, with O(h) stack space.",
        "I'd quote the height whenever I talk about how costly a tree walk or a search can be.",
        filenames=(),
        procedures=("Height",),
    ),
    _explainer(
        "heapsort",
        "Heapsort",
        "Heapsort builds a max-heap, then repeatedly swaps the root with the last heap cell, shrinks the heap, and sifts the new root down.",
        "Sift restores the heap rule by swapping a node with its larger child until the rule holds. Heapify sifts every parent, from the last one back to the root. Then each round moves the largest remaining item into place.",
        "Building the heap is O(n), and each of the n later sifts is O(log n), so the sort is O(n log n) even in the worst case and uses only O(1) extra space.",
        "It is not stable: equal items can change order as they swap. I'd use it when I need a guaranteed n log n bound and can work in place. This listing uses 1-based indexes, where the children of i are 2i and 2i + 1.",
        filenames=("heap",),
        procedures=("HeapSort",),
    ),
    _explainer(
        "union-find",
        "Union-find",
        "Union-find keeps items in groups. Find walks parent pointers until it reaches a node that is its own parent, and that node is the representative. Unite joins two groups by hanging one root under the other, but only if they are not already together.",
        "Find climbs until parent(x) is x, and returns x. Unite finds both roots and, if they differ, points one at the other.",
        "Without extra rules, a chain of unions can make Find O(n). With a weighting rule the walk is O(log n), and with path compression as well a sequence of operations is effectively constant time per operation.",
        "Careless unions that always hang the same way can build a single long stick. I'd use union-find whenever I have to keep asking whether two names already belong together, as Kruskal's algorithm does.",
        filenames=("union_find",),
        procedures=("Unite",),
    ),
    _explainer(
        "dfs",
        "Depth-first search",
        "Depth-first search walks as far as it can along one path, then backs up. I mark a vertex as I enter it, record it, and recurse on each unseen neighbor.",
        "On entry I mark the vertex seen, append it to the visit order, and walk each unused neighbor in turn.",
        "With adjacency lists I look at each vertex and each edge a constant number of times, so the time is O(n + m). The call stack, and the seen marks, use O(n) space.",
        "I have to mark vertices as seen, or a cycle would loop forever. I'd use a depth-first walk to detect cycles, to produce a topological order, or to find components.",
        filenames=(),
        procedures=("Visit",),
    ),
    _explainer(
        "bfs",
        "Breadth-first search",
        "Breadth-first search visits vertices level by level from the start, using a queue: I take the next vertex from the front and append each unseen neighbor at the back.",
        "I start the queue with the source, marked seen. While the queue is not empty I take the front vertex, record it, and enqueue each unseen neighbor, marking it as it joins the queue.",
        "Like depth-first search, it is O(n + m) time with adjacency lists and O(n) extra space for the queue and the seen marks.",
        "Mark a neighbor as soon as it joins the queue, or it may be enqueued twice. I'd use this for shortest paths in an unweighted graph, because the first time I reach a vertex is along a shortest route.",
        filenames=(),
        procedures=("Breadth",),
    ),
    _explainer(
        "dijkstra",
        "Dijkstra's algorithm",
        "Dijkstra finds the cheapest path from one start to every other vertex, as long as no weight is negative.",
        "Each round I settle the unsettled vertex whose current distance is smallest, then try to relax its outgoing edges: if a route through that vertex is cheaper, I update the distance.",
        "This listing scans all vertices to pick the next one, so it takes O(n^2) time and O(n) extra space for the distance and used marks. A min-heap would make the same idea O((n + m) log n).",
        "I would not use it if a negative edge could appear, because a settled distance might then be wrong. Unreachable vertices keep a stand-in for infinity.",
        filenames=("paths",),
        procedures=("Shortest",),
    ),
    _explainer(
        "kruskal",
        "Kruskal's algorithm",
        "Kruskal builds a cheapest spanning tree by considering edges in order of cost and adding an edge only when its ends are in different components.",
        "I sort the edges cheapest first. For each edge I ask union-find whether its two ends already belong together; if they do not, I add the edge and unite the two groups.",
        "The sort dominates, so the time is O(m log m) for m edges, and the parent array uses O(n) space.",
        "An edge that would close a loop is refused. I'd use it when I want a cheapest network that joins every vertex.",
        filenames=("paths",),
        procedures=("Shortest", "Find"),
    ),
    _explainer(
        "digits",
        "Adding long numbers",
        "To add two long numbers, I walk their digits from the low end, add the two digits and the carry, write a single digit, and keep the new carry.",
        "At each position I add the two digits (or 0 if that number is shorter) plus the carry, write the result mod 10, and set the carry to the tens digit. I continue while either number still has digits or a carry remains.",
        "The loop runs once per digit of the longer number, plus once more if a final carry remains, so the time is O(n) and the result uses O(n) space.",
        "Forgetting that last carry is the usual bug: 99 + 1 must grow an extra digit. I'd use this whenever a number is too long for one machine word.",
        filenames=("digits",),
        procedures=("Add",),
    ),
    _explainer(
        "atoms",
        "Walking the atoms of a list",
        "To list the atoms of a generalized list, I look at the tag first: if the cell is an atom I print it, and if it is a list I walk its head and then its tail.",
        "A nil pointer returns at once. A tag of 0 is an atom, so I output its value. A tag of 1 is a list cell, so I recurse on head and then on tail.",
        "Each cell is visited once, so the time is O(n), and the call stack is as deep as the nesting, which is O(n) in the worst case.",
        "This walk is safe on a pure list, which has the shape of a tree. On a list with sharing or a cycle it can repeat work or loop forever, so I'd use a mark, or an explicit stack, for those cases.",
        filenames=("atoms",),
        procedures=("Atoms",),
    ),
    _explainer(
        "hash",
        "A chained hash table",
        "A hash table maps a key to a slot, and chaining stores in each slot a linked list of the keys that hashed there. The division method uses key mod m.",
        "To insert, I hash the key and push a new node at the front of that slot's chain. A search hashes the key and walks only that chain.",
        "If the keys spread out, each chain stays short and insert or search is expected O(1). If they all collide, a chain can grow to O(n), so the worst case is linear. The table uses O(n + m) space.",
        "I'd keep m from being a power of two when I use division, because then only the lowest bits of the key would matter. I'd use chaining when I want deletions to be simple and I can let a slot hold more than one key.",
        filenames=("hash",),
        procedures=("Put",),
    ),
]


# Kruskal is more specific than Dijkstra (extra Find) and should be
# reported in addition to Dijkstra, not instead of it. Same for Linear
# and Binary in one file, or Pre and Height, or Visit and Breadth.
_COEXIST = frozenset(
    {
        frozenset({"dijkstra", "kruskal"}),
        frozenset({"linear", "binary"}),
        frozenset({"linear", "find-binary"}),
        frozenset({"preorder", "height"}),
        frozenset({"dfs", "bfs"}),
        frozenset({"bst", "height"}),
    }
)


def procedure_names(source: str) -> set[str]:
    """Return the procedure names defined in an Easy program."""
    names = set()
    for match in re.finditer(
        r"(?im)^procedure\s+([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z0-9]*)*)",
        source,
    ):
        names.add(match.group(1).split("(")[0].strip())
    return names


def stem_of(name: str | None) -> str:
    if not name:
        return ""
    # URLs: use the last path segment
    leaf = name.rstrip("/").split("/")[-1]
    return Path(leaf).stem.lower()


def _comment_explainer(source: str) -> Explainer | None:
    """Build an explainer from `¤ Interview:` comments, if they look complete."""
    comments: list[str] = []
    taking = False
    for raw in source.splitlines():
        stripped = raw.strip()
        if stripped.startswith("¤"):
            body = stripped[1:].strip()
            if body.lower().startswith("interview:"):
                taking = True
                rest = body.split(":", 1)[1].strip()
                if rest:
                    comments.append(rest)
                continue
            if taking:
                comments.append(body)
                continue
        elif taking and stripped == "":
            continue
        elif taking:
            break
    if not comments:
        return None
    # Optional labeled lines: Key steps / Cost / Watch
    does: list[str] = []
    steps: list[str] = []
    cost: list[str] = []
    watch: list[str] = []
    bucket = does
    for line in comments:
        low = line.lower()
        if low.startswith("key steps:"):
            bucket = steps
            line = line.split(":", 1)[1].strip()
        elif low.startswith(("time and space:", "cost:")):
            bucket = cost
            line = line.split(":", 1)[1].strip()
        elif low.startswith(("watch for:", "watch:")):
            bucket = watch
            line = line.split(":", 1)[1].strip()
        if line:
            bucket.append(line)
    if not does:
        return None
    return Explainer(
        id="source",
        title="This program",
        does=" ".join(does),
        steps=" ".join(steps),
        cost=" ".join(cost),
        watch=" ".join(watch),
    )


def _catalog_matches(source: str, name: str | None) -> list[Explainer]:
    procs = procedure_names(source)
    procs.discard("MAIN")
    stem = stem_of(name)
    found: list[Explainer] = []
    for entry in CATALOG:
        if entry.markers and any(marker not in source for marker in entry.markers):
            continue
        if entry.procedures and entry.procedures <= procs:
            found.append(entry)
            continue
        if not entry.procedures and stem and stem in entry.filenames:
            found.append(entry)
    # Drop a match whose procedures are a proper subset of a more
    # specific match, unless the pair is allowed to coexist.
    ids = {entry.id for entry in found}
    keep: list[Explainer] = []
    for entry in found:
        superseded = False
        for other in found:
            if other is entry or not entry.procedures or not other.procedures:
                continue
            if entry.procedures < other.procedures:
                pair = frozenset({entry.id, other.id})
                if pair not in _COEXIST:
                    superseded = True
                    break
        if not superseded:
            keep.append(entry)
    # Filename can add a nodes/links match that has no procedures.
    # Prefer stable catalog order.
    order = {entry.id: i for i, entry in enumerate(CATALOG)}
    keep.sort(key=lambda entry: order[entry.id])
    # If Find and Binary both matched, they are the same algorithm.
    ids = [entry.id for entry in keep]
    if "binary" in ids and "find-binary" in ids:
        keep = [entry for entry in keep if entry.id != "find-binary"]
    return keep


def lookup(source: str, name: str | None = None) -> list[Explainer]:
    """Return the explainer(s) that apply to this program."""
    owned = _comment_explainer(source)
    if owned is not None:
        return [owned]
    return _catalog_matches(source, name)


def format_explainer(entry: Explainer, heading: bool = True) -> str:
    """Format one explainer as plain words."""
    parts: list[str] = []
    if heading:
        if entry.title and entry.id != "source":
            parts.append(f"How to explain it in an interview: {entry.title}")
        else:
            parts.append("How to explain it in an interview")
        parts.append("")
    parts.append(entry.does)
    if entry.steps:
        parts.append("")
        parts.append(f"Key steps: {entry.steps}")
    if entry.cost:
        parts.append("")
        parts.append(f"Time and space: {entry.cost}")
    if entry.watch:
        parts.append("")
        parts.append(f"Watch for: {entry.watch}")
    return "\n".join(parts).strip() + "\n"


def explain_interview(source: str, name: str | None = None) -> str:
    """Return the interview explainer text for an Easy program.

    Raises InterviewError if the program is not yet in the catalog and
    does not carry its own `¤ Interview:` comments.
    """
    matches = lookup(source, name)
    if not matches:
        label = name or "this program"
        raise InterviewError(f"no interview explainer for {label}")
    if len(matches) == 1:
        return format_explainer(matches[0], heading=True)
    blocks = [format_explainer(entry, heading=True) for entry in matches]
    return "\n".join(blocks)


__all__ = [
    "Explainer",
    "InterviewError",
    "explain_interview",
    "format_explainer",
    "lookup",
    "procedure_names",
]
