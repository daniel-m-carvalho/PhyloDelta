# The maximum agreement subtree of two rooted trees, by phangorn: the test
# oracle for PhyloDelta's own MAST (metrics/plugins/mast, DECISIONS §46).
#
#   Rscript tools/mast_phangorn.R left.nwk right.nwk
#
# Prints, tab-separated:
#   mast_size  <leaves in the maximum agreement subtree>
#   kept       <label>      one line per leaf in it
#
# `tree = FALSE` matters: with phangorn's default `tree = TRUE`, mast() returns
# a tree, and taking setdiff() of a tree as if it were a vector of labels
# reports every leaf as moved.
suppressPackageStartupMessages({
  library(ape)
  library(phangorn)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
  stop("usage: Rscript mast_phangorn.R left.nwk right.nwk", call. = FALSE)
}
kept <- mast(read.tree(args[[1]]), read.tree(args[[2]]), tree = FALSE, rooted = TRUE)

cat("mast_size\t", length(kept), "\n", sep = "")
for (label in kept) cat("kept\t", label, "\n", sep = "")
