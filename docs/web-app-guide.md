# Using the web app

PhyloDelta shows two trees side by side, the **left** and the **right** tree, coloured by how much
they agree. This guide walks through every task, each with a short video. For what the colours and
shapes mean, see [Reading a comparison](reading-a-comparison.md).

> Click a video's picture to play it.

## Contents

1. [Upload two trees](#1-upload-two-trees)
2. [Open a comparison](#2-open-a-comparison)
3. [Navigate a tree](#3-navigate-a-tree)
4. [Search for a leaf](#4-search-for-a-leaf)
5. [Find a leaf in the other tree](#5-find-a-leaf-in-the-other-tree)
6. [View options](#6-view-options)
7. [Isolate data](#7-isolate-data)
8. [Export a report](#8-export-a-report)
9. [Remove a comparison](#9-remove-a-comparison)

---

## 1. Upload two trees

[![Uploading two trees](videos/01-upload.png)](videos/01-upload.mp4)

On the home page, under **New comparison**:

1. Drop a Newick file (`.nwk`, `.newick`, `.tree`) on **Left tree** and another on **Right tree**,
   or click them to choose a file.
2. *Optional:* **Isolate data**, a tab-separated table (`.tsv`) describing the isolates behind each
   leaf (source, country, year…). Keep **One table for both trees** ticked when both trees are the
   same organism; untick it to give each tree its own table.
3. *Optional:* a **Name** for the comparison (by default, the two file names), and the **Left
   species** / **Right species**. Naming the species lets the result say whether matching leaf names
   really are the same organisms. Sequence types are numbered per species, so across species the same
   number is a coincidence.
4. Choose what to **Compare with** (the metric). Under the choice, "Computed as in…" says where the
   metric's computation comes from.
5. Click **Upload and compare**.

The comparison is computed on the server in the background. The panel shows **Queued — waiting for a
worker**, then **Computing the comparison…**, then opens the comparison when it is ready. Large trees can take minutes. You can leave
the page and come back: the comparison appears in your list when it is done. If one of several
metrics could not be computed, the panel says which and why; the rest of the comparison is still
usable.

## 2. Open a comparison

[![Opening a comparison](videos/02-open-comparison.png)](videos/02-open-comparison.mp4)

**Your comparisons**, on the home page, lists every comparison you have, with how many leaves the two
trees share and which metrics were computed. Click one to open it. **← Back** (top right) returns to
the list.

The address in your browser's bar always names what is on screen, including how far you have
navigated and the view options. Bookmark it, refresh, or send it to someone, and the same view opens.

## 3. Navigate a tree

[![Navigating a tree](videos/03-navigate.png)](videos/03-navigate.mp4)

A tree too large to draw whole is shown as a summary: the biggest groups of leaves are drawn as
**triangles** (collapsed clades), sized by how many leaves they hold. You go deeper by opening them.

- **Zoom and move:** scroll to zoom, drag to move, in either panel. This only enlarges what is
  already drawn.
- **Open a clade:** right-click a triangle, then **Expand this clade**. The panel then shows that
  clade alone, in more detail. On any other internal point, the same menu offers **Focus this
  subtree**.
- **Go back:** right-click empty space, then **Go back** (one level out), or **Reset to the whole
  tree**.
- **Expand all / Collapse all** (right-click empty space): draw every leaf of what is on screen, or
  fold it to its outline. "Expand all" is offered only when the result is small enough to draw.
- **Select, then act:** click a node to select it ("node … selected" appears in the header), then
  right-click anywhere in that panel to act on it, which is handy for nodes too small to hit.

The header above each panel says **showing N of M leaves**: N drawn, M in the part of the tree on
screen, and how many are folded into triangles.

## 4. Search for a leaf

[![Searching for a leaf](videos/04-search.png)](videos/04-search.mp4)

Type a leaf's name in **Find a node by name** above the panels. In the demo trees the names are
sequence types, e.g. `1203`. Results appear as you type, the exact name first, then names that start
with it, with ✓ or ✗ for each tree:

```
Name        Left  Right
1203         ✓     ✓
12030        ✓     ✗
```

Click a result. Each panel that has the leaf moves to it and marks it (it blinks, then stays
highlighted). A panel whose tree does not have it stays where it is and says so in a short message
that fades after a few seconds.

## 5. Find a leaf in the other tree

[![Finding a leaf in the other tree](videos/05-find-in-other-tree.png)](videos/05-find-in-other-tree.mp4)

Right-click a leaf in one panel, then **Find this leaf in the other tree**. The other panel moves to
the same leaf, shown with enough of its surroundings to read, and marks it. The header names it:

- **Found: 1203**, the leaf itself is drawn and marked.
- **Found inside: 1203 (in this clade)**, the leaf is inside a triangle too large to open at this
  level of detail. The triangle that holds it is marked; open it to reach the leaf.
- **Found: 1203 (outside this view)**, you have moved to a part of the tree that does not contain
  it. Go back to see it again.

The mark stays until you clear it with **×** on the chip, or **Esc**.

## 6. View options

[![View options](videos/06-view-options.png)](videos/06-view-options.mp4)

**View options** (top right) holds every display setting:

| Option | What it does |
|---|---|
| **Divergence** | Colour the trees by how much they disagree (see [Reading a comparison](reading-a-comparison.md)). |
| **Colour the divergence on: Branches / Clades** | Put the colour on the branches, or on the collapsed triangles. |
| **Isolate data** | A bar on each leaf counting its isolates ([section 7](#7-isolate-data)). |
| **Clade sizes** | Label every triangle with its number of leaves. |
| **Branch lengths** | Write each branch's length beside it, where there is room. Zoom in to see more. |
| **Draw the trees as: Cladogram / Phylogram** | Cladogram: positions by depth, to read the shape. Phylogram: positions by branch length, to read distance. |
| **Branch length scale: Linear / Logarithmic** | Phylogram only. Logarithmic draws each branch as log(1 + length), so a few very long branches no longer squash the rest. Labels still show the real length. |

## 7. Isolate data

[![Isolate data](videos/07-isolate-data.png)](videos/07-isolate-data.mp4)

When a tree has isolate data, turn on **View options → Isolate data**. Each leaf gets a bar whose
length is its number of isolates, split into colours by a column of the table:

- **Colour by:** choose one or more columns (e.g. Source Niche, Country).
- **Bar length:** Logarithmic (default, since counts vary a lot) or Linear.
- **Change a colour:** click a colour square in the legend and pick a new colour. **Reset colours**
  restores the originals. Chosen colours are kept in the page address, so they survive a refresh and
  appear in exported reports.

A leaf with no bar has no isolate data. "(not recorded)" counts isolates with an empty value in that
column.

## 8. Export a report

[![Exporting a report](videos/08-export.png)](videos/08-export.mp4)

**Export** (top right) produces a report of the comparison: its scores, what the colours mean, and,
if you keep **Include the two trees as they look now** ticked, pictures of both panels exactly as you
have them. Choose **HTML** (selectable text, full-size pictures), **PDF** (for printing or attaching)
or **PNG** (one image, for slides).

## 9. Remove a comparison

[![Removing a comparison](videos/09-remove.png)](videos/09-remove.mp4)

In **Your comparisons**, the **×** beside a comparison removes it, with the trees and isolate data
that only it was using, after asking you to confirm. Trees another comparison still needs are kept.
This cannot be undone.
