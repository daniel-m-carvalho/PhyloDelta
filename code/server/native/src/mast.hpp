// Maximum agreement subtree of two rooted binary trees (DECISIONS §46).
//
// The recurrence of Steel & Warnow (1993), over internal x internal clades:
//
//   M[u,v] = max(M[u1,v1] + M[u2,v2], M[u1,v2] + M[u2,v1],
//                M[u,v1], M[u,v2], M[u1,v], M[u2,v])
//
// A pair involving a leaf is answered from leaf-order intervals, so the table
// holds internal clades only. One integer per cell — not a list of labels, as
// phangorn keeps — is what takes the demo pair from a crash at 8 GB to a few
// hundred MB.
//
// Mirrors agreement_python in metrics/plugins/mast/mast.py term for term,
// including which term wins a tie, and is checked against it for equality.

#pragma once

#include <cstdint>
#include <utility>
#include <vector>

namespace phylodelta {

struct MastInput {
    const int64_t* left_end;
    const int64_t* right_end;
    const int64_t* left_in_right;  // a left leaf's position in the right leaf order
    const int64_t* right_in_left;  // a right leaf's position in the left leaf order
    const int64_t* left_lo;
    const int64_t* left_hi;
    const int64_t* right_lo;
    const int64_t* right_hi;
    const int64_t* left_position;  // a left leaf's position in its own leaf order
    int64_t n_left;
    int64_t n_right;
};

namespace detail {

template <typename Cell>
std::vector<uint8_t> mast_with(const MastInput& in) {
    const int64_t* le = in.left_end;
    const int64_t* re = in.right_end;

    std::vector<int64_t> row(in.n_left, -1), col(in.n_right, -1);
    std::vector<int64_t> left_internal, right_internal;
    for (int64_t u = 0; u < in.n_left; ++u)
        if (le[u] != u + 1) { row[u] = static_cast<int64_t>(left_internal.size()); left_internal.push_back(u); }
    for (int64_t v = 0; v < in.n_right; ++v)
        if (re[v] != v + 1) { col[v] = static_cast<int64_t>(right_internal.size()); right_internal.push_back(v); }

    const size_t width = right_internal.size();
    std::vector<Cell> table(left_internal.size() * width, 0);

    auto value = [&](int64_t u, int64_t v) -> int64_t {
        if (le[u] == u + 1)
            return in.right_lo[v] <= in.left_in_right[u] && in.left_in_right[u] <= in.right_hi[v];
        if (re[v] == v + 1)
            return in.left_lo[u] <= in.right_in_left[v] && in.right_in_left[v] <= in.left_hi[u];
        return table[static_cast<size_t>(row[u]) * width + static_cast<size_t>(col[v])];
    };

    // The six terms, in the order agreement_python lists them.
    auto terms = [&](int64_t u, int64_t v, int64_t out[6]) {
        const int64_t u1 = u + 1, u2 = le[u + 1];
        const int64_t v1 = v + 1, v2 = re[v + 1];
        out[0] = value(u1, v1) + value(u2, v2);
        out[1] = value(u1, v2) + value(u2, v1);
        out[2] = value(u, v1);
        out[3] = value(u, v2);
        out[4] = value(u1, v);
        out[5] = value(u2, v);
    };

    // Children follow their parent in pre-order: walking both trees backwards
    // fills every cell a cell depends on first.
    int64_t t[6];
    for (auto ui = left_internal.rbegin(); ui != left_internal.rend(); ++ui) {
        Cell* cells = table.data() + static_cast<size_t>(row[*ui]) * width;
        for (auto vi = right_internal.rbegin(); vi != right_internal.rend(); ++vi) {
            terms(*ui, *vi, t);
            int64_t best = t[0];
            for (int k = 1; k < 6; ++k) best = t[k] > best ? t[k] : best;
            cells[col[*vi]] = static_cast<Cell>(best);
        }
    }

    const int64_t n_leaves = in.left_hi[0] + 1;
    std::vector<uint8_t> kept(static_cast<size_t>(n_leaves), 0);
    std::vector<std::pair<int64_t, int64_t>> stack{{0, 0}};
    while (!stack.empty()) {
        auto [u, v] = stack.back();
        stack.pop_back();
        if (le[u] == u + 1) {
            if (value(u, v)) kept[static_cast<size_t>(in.left_position[u])] = 1;
            continue;
        }
        if (re[v] == v + 1) {
            if (value(u, v)) kept[static_cast<size_t>(in.right_in_left[v])] = 1;
            continue;
        }
        const int64_t best = value(u, v);
        if (best == 0) continue;
        terms(u, v, t);
        const int64_t u1 = u + 1, u2 = le[u + 1];
        const int64_t v1 = v + 1, v2 = re[v + 1];
        // The first term reaching the best, as agreement_python takes it.
        if (t[0] == best) { stack.push_back({u1, v1}); stack.push_back({u2, v2}); }
        else if (t[1] == best) { stack.push_back({u1, v2}); stack.push_back({u2, v1}); }
        else if (t[2] == best) stack.push_back({u, v1});
        else if (t[3] == best) stack.push_back({u, v2});
        else if (t[4] == best) stack.push_back({u1, v});
        else stack.push_back({u2, v});
    }
    return kept;
}

}  // namespace detail

// Which left leaves (by position in the left leaf order) the MAST keeps.
// Two-byte cells while every count fits in them; four otherwise.
inline std::vector<uint8_t> mast(const MastInput& in) {
    const int64_t n_leaves = in.left_hi[0] + 1;
    if (n_leaves <= 0xFFFF) return detail::mast_with<uint16_t>(in);
    return detail::mast_with<uint32_t>(in);
}

}  // namespace phylodelta
