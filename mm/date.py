def dag_vd_week(day, month, year):
    if month <= 2:
        month += 12
        year -= 1
    
    q = day
    m = month
    K = year % 100
    J = year // 100

    h = (q + (13*(m+1))//5 + K + (K//4) + (J//4) + 5*J) % 7
    days = ["Saturday", "Sunday", "Monday", "Tuesday", 
            "Wednesday", "Thursday", "Friday"]
    return days[h]

def main():
    print("Voer datum in (YYYY/MM/DD)")
    user_input = input("> ")

    try:
        year, month, day = map(int, user_input.split("/"))
        dagnaam = dag_vd_week(day, month, year)
        print(f"De datum {user_input} valt op een {dagnaam}.")
    except Exception:
        print("Fout: Zorg dat je het formaat YYYY/MM/DD gebruikt.")


if __name__ == "__main__":
    main()
