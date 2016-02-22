#include <memory>
#include <iostream>

class X {
 public:
  X() : data(0) {
    std::cout << "-> X()\n";
  }

  explicit X(const int n) : data(n) {
    std::cout << "-> explicit X(" << n << ")\n";
  }

  ~X() {
    std::cout << "-> ~X(" << data << ")\n";
  }

  friend std::ostream& operator<<(std::ostream& out, const X& x) {
    out << "x = " << x.data;
    return out;
  }

 private:
  int data;
};

// Capture by reference, std::unique_ptr has no copy constructor.
void print_x(const std::unique_ptr<X>& x) {
  std::cout << *x << std::endl;
}

// Capture by value.
void print_x(const std::shared_ptr<X> x) {
  std::cout << *x << std::endl;
}

int main() {
  const auto a = std::make_unique<X>(10);
  const std::unique_ptr<X> b{new X(11)};
  const auto c = std::make_shared<X>(12);

  print_x(a);
  print_x(b);
  print_x(c);

  return 0;
}
