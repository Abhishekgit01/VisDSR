// DSU simulator. Build: g++ -std=c++17 -O2 -Wall -Wextra -pedantic sim/dsu.cpp -o sim/dsu
#include <iostream>
#include <stdexcept>
#include <vector>

class DSU {
 public:
  explicit DSU(int n) : parent_(n), size_(n, 1) {
    for (int i = 0; i < n; ++i) parent_[i] = i;
  }

  int find(int x) {
    int root = x;
    while (parent_[root] != root) root = parent_[root];

    // Rewrite every edge on the traversed path to point to the root.
    while (parent_[x] != x) {
      int next = parent_[x];
      parent_[x] = root;
      x = next;
    }
    return root;
  }

  void unite(int a, int b) {
    int root_a = find(a);
    int root_b = find(b);
    if (root_a == root_b) return;

    // Keep root_a on an equal-size tie: root_b must attach below it.
    if (size_[root_a] < size_[root_b]) {
      int temp = root_a;
      root_a = root_b;
      root_b = temp;
    }
    parent_[root_b] = root_a;
    size_[root_a] += size_[root_b];
  }

  const std::vector<int>& parents() const { return parent_; }

 private:
  std::vector<int> parent_;
  std::vector<int> size_;
};

// Protocol: n prelude_count task_count, followed by lines "U a b" or "F a 0".
// Prelude operations build the reachable initial state; task operations are
// reported as JSON. Indices are zero-based; emitted labels are A..Z.
static void print_state(const DSU& dsu) {
  std::cout << '{';
  const auto& p = dsu.parents();
  for (size_t i = 0; i < p.size(); ++i) {
    if (i) std::cout << ',';
    std::cout << '"' << char('A' + i) << "\":\"" << char('A' + p[i]) << '"';
  }
  std::cout << '}';
}

int main() {
  try {
    int n, prelude, count;
    if (!(std::cin >> n >> prelude >> count) || n < 1 || n > 26 ||
        prelude < 0 || count < 0) throw std::runtime_error("invalid header");
    DSU dsu(n);
    for (int i = 0; i < prelude + count; ++i) {
      char kind;
      int a, b;
      if (!(std::cin >> kind >> a >> b) || a < 0 || a >= n ||
          (kind == 'U' && (b < 0 || b >= n)) || (kind != 'U' && kind != 'F'))
        throw std::runtime_error("invalid operation");
      int result = -1;
      if (kind == 'U') dsu.unite(a, b);
      else result = dsu.find(a);
      if (i == prelude - 1) {
        std::cout << "{\"initial\":";
        print_state(dsu);
        std::cout << ",\"steps\":[";
      }
      if (i >= prelude) {
        if (i == prelude && prelude == 0) {
          std::cout << "{\"initial\":";
          // The generator always uses a nonempty prelude. This branch supports
          // standalone unit tests with an empty prelude.
          DSU fresh(n);
          print_state(fresh);
          std::cout << ",\"steps\":[";
        }
        if (i > prelude) std::cout << ',';
        std::cout << "{\"state\":";
        print_state(dsu);
        if (kind == 'F') std::cout << ",\"find_result\":\"" << char('A' + result) << '"';
        std::cout << '}';
      }
    }
    if (prelude == 0 && count == 0) {
      std::cout << "{\"initial\":";
      print_state(dsu);
      std::cout << ",\"steps\":[";
    }
    std::cout << "]}\n";
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
