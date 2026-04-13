import sqlite3
import os

db_path = r"C:\Litonsir\real_estate.db"

data = {
    "A1": "Dewan Mohammad Tushar",
    "A2": "Afsana Sharmin",
    "A3": "Arif Sultan Mahmud",
    "A4": "Khairun Tahmina",
    "A5": "Aslam Dewan",
    "A6": "Mizanur Rahman",
    "A7": "Tahmina Yeasmin",
    "A8": "Mirza Shahir",
    "A9": "Jannatin Naima",
    "A10": "S.K.M Moklesur Rahman",
    "A11": "Jahanara Sultan",
    "B1": "Fazle Rabbi",
    "B2": "Akramul Alam",
    "B3": "Siblee Sadiq",
    "B4": "Dibendu Singha Bapon",
    "B5": "Syed Fakhrul Hasan",
    "B6": "S.M Bazlur Rashid",
    "B7": "Bazlur Rahman",
    "B8": "Abdullah Al Mamun",
    "B9": "Md. Sajidur Rahman",
    "B10": "Rezwanul Kabir",
    "B11": "Jahanara Sultan",
    "C1": "Abdul Goni",
    "C2": "Naznin Sultana",
    "C3": "Jahanara Sultan",
    "C4": "Shah Alam Sarder",
    "C5": "Jahanara Sultan",
    "C6": "Saima Khatun",
    "C7": "Shahida Arabi",
    "C8": "A.K.M Abdur Raqib",
    "C9": "Dilara Begun",
    "C10": "Salauddin Shopon",
    "C11": "Shah Alam Sarder",
    "D1": "Nazma Begum",
    "D2": "Bikis Jamal",
    "D3": "Jahanara Sultan",
    "D4": "Shahanaz Parvin",
    "D5": "Nurun Nahar Zaman",
    "D6": "Dr. Sanjida Parveen",
    "D7": "Akram Hossain",
    "D8": "A.S.M Hasan Ali Masum",
    "D9": "Swapon Kumar Sengupta",
    "D10": "Shahadat Hossain",
    "D11": "Jahanara Sultan",
    "E1": "Azharul Islam",
    "E2": "Mahabub Hasan Mukul",
    "E3": "Jahanara Sultan",
    "E4": "Prof. Md Mazharul Hannan",
    "E5": "Jahanara Sultan",
    "E6": "Aditi Das",
    "E7": "Jahanara Sultan",
    "E8": "Md. Zahidul Islam",
    "E9": "Abul Kalam",
    "E10": "Sharif Mahmud",
    "E11": "Md. Anisur Rahman",
    "F1": "Jahanara Sultan",
    "F2": "Md. Raquibur Rahman",
    "F3": "Jahanara Sultan",
    "F4": "Jubayer Rahman",
    "F5": "Jahanara Sultan",
    "F6": "Tareq Hasan",
    "F7": "Jahanara Sultan",
    "F8": "Rokan Uddin Ahmed Reza",
    "F9": "Abdullah Hil Kafi",
    "F10": "Salauddin",
    "F11": "Hasan Shakil Ahmed",
    "G1": "Mahabub Alam",
    "G2": "Afroza Akter",
    "G3": "Jahanara Sultan",
    "G4": "Lutfof Rahman",
    "G5": "Reazul Islam",
    "G6": "Aklima Islam",
    "G7": "Jannatul Ferdous",
    "G8": "Tareq Hasan Prodhan",
    "G9": "Md. Mostafizur Rahman",
    "G10": "Salauddin Shopon",
    "G11": "Bedoura Farhana",
    "H1": "Jahanara Sultan",
    "H2": "Abeer Muttafiqur Raheman",
    "H3": "Arif Sultan Mahmud",
    "H4": "Farhad Reza",
    "H5": "Rahat Parvin",
    "H6": "Rumana Islam",
    "H7": "Jahanara Sultan",
    "H8": "Masuma Khtun",
    "H9": "Mohammad Ali",
    "H10": "Md. Masud Reza Jowarder",
    "H11": "Md. Mahsin",
}

def assign_customers():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    customer_count = 0
    assigned_count = 0

    # Cache for customer names to IDs
    customer_cache = {}

    for unit_num, customer_name in data.items():
        # Get or create customer
        if customer_name in customer_cache:
            customer_id = customer_cache[customer_name]
        else:
            cursor.execute("SELECT id FROM customer WHERE name = ?", (customer_name,))
            res = cursor.fetchone()
            if res:
                customer_id = res[0]
            else:
                cursor.execute("INSERT INTO customer (name) VALUES (?)", (customer_name,))
                customer_id = cursor.lastrowid
                customer_count += 1
            customer_cache[customer_name] = customer_id

        # Link to unit
        cursor.execute("UPDATE unit SET customer_id = ?, status = 'occupied' WHERE unit_number = ?", (customer_id, unit_num))
        if cursor.rowcount > 0:
            assigned_count += 1
        else:
            print(f"Warning: Unit {unit_num} not found in database.")

    conn.commit()
    conn.close()

    print(f"Created {customer_count} new customer records.")
    print(f"Assigned {assigned_count} units to customers and set status to 'occupied'.")

if __name__ == "__main__":
    assign_customers()
