# $ cat curves.txt | grep -v '^20\s*25' | paste -sd ' \n' > curves_joined.txt
with open("curves_joined.txt") as f:
    data = f.read()

table = []
for row in data.strip().split("\n"):
    B1, B2, *vals = row.split()
    B1, B2 = int(B1), int(B2)
    int_vals = []
    for val in vals:
        if not val.isdigit():
            break
        int_vals.append(int(val))
    print (f"{B1=} {B2=} | {vals}")
    print (f"{B1=} {B2=} | {int_vals}")
    assert int_vals == sorted(int_vals)
    if int_vals:
        table.append([B1, B2, *int_vals])

print ("curve_data =", table)

