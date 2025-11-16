def add(a, b):
    return a + b
def sub(a, b):
    return a - b
def mult(a, b):
    return a * b
def div(a, b):
    if b == 0:
        return "kan niet delen door 0"
    return a / b

def main():
    print("kies (add, sub, mult, dev):")
    op = input("> ")
    a = float(input("voer het eerste nummer in"))
    b = float(input("voer het tweede nummer in"))

    if op == "add":
        print("Resultaat:", add(a, b))
    elif op == "sub":
        print("Resultaat:", sub(a, b))
    elif op == "mult":
        print("Resultaat:", mult(a, b))
    elif op == "div":
        print("Resultaat:", div(a, b))

if __name__ == "__main__":
    main()


