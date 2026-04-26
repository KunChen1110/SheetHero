import os
import random
from openpyxl import Workbook

# Folder to save the Excel files
OUTPUT_FOLDER = "."
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Sample data pools
names = [
    "Alice Johnson", "Bob Miller", "Charlie Smith", "Diana Rose", "Ethan Green",
    "Fiona Brown", "George White", "Hannah Black", "Ivan Gray", "Julia Watson",
    "Kevin Ford", "Linda Hall", "Michael Lee", "Nina Adams", "Oscar Clark",
    "Paula King", "Quentin Young", "Rachel Scott", "Sam Turner", "Tina Lopez"
]

skills_pool = [
    "python", "Java", "c++", "SQL", "Machine learning", "data analysis",
    "Communication", "Leadership", "Javascript", "Project mgmt"
]

education_levels = ["Bachelor", "Master", "PHD", "diploma", "BSc", "MSc"]

companies = [
    "Google", "Amazon", "Microsoft", "StartupX", "ByteWave", "",
    "FinTechLab", "BrightAI", "NextVision", "DataHub"
]


def random_skills():
    chosen = random.sample(skills_pool, random.randint(2, 5))
    # Add random spacing & inconsistent formatting
    noisy = [skill + (" " * random.randint(0, 3)) for skill in chosen]
    return ", ".join(noisy)


def random_past_companies():
    chosen = random.sample(companies, random.randint(1, 3))
    return ", ".join(chosen)


def maybe_missing(value):
    """Randomly remove some fields to simulate missing or incomplete data."""
    return value if random.random() > 0.2 else ""


def generate_excel(index, name):
    wb = Workbook()
    ws = wb.active

    # Some headers purposely messy / inconsistent
    headers = [
        "Name", "age ", "YearsOfExperience", " Key Skills",
        "EDUCATION", "expected salary", "Personality Score ",
        "Past companies"
    ]

    values = [
        name,
        random.randint(22, 45),
        random.randint(0, 15),
        random_skills(),
        random.choice(education_levels),
        random.randint(30000, 150000),
        round(random.uniform(1.0, 5.0), 2),
        random_past_companies()
    ]

    # Write messy headers + possibly missing values
    ws.append(headers)
    ws.append([maybe_missing(str(v)) for v in values])

    # Save as tc21_inputXX.xlsx
    filename = f"tc21_input{index:02d}.xlsx"
    filepath = os.path.join(OUTPUT_FOLDER, filename)
    wb.save(filepath)

    print(f"Generated: {filepath}")


# Generate 20 Excel mini-tables
for i in range(1, 21):
    generate_excel(i, names[i - 1])

print("\nAll 20 Excel interview mini-tables created successfully!")
