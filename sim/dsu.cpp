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
    // TODO: follow parent pointers, compress the full path, and return the root.
    (void)x;
    throw std::logic_error("DSU::find is not implemented");
  }

  void unite(int a, int b) {
    // TODO: call find(a) and find(b) first, even if already connected.
    // Attach the smaller root under the larger root. On an equal-size tie,
    // attach b's root under a's root. Update size_ only after a real merge.
    (void)a;
    (void)b;
    throw std::logic_error("DSU::unite is not implemented");
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
