# Universal Testing Machine (UTM) Professional - User Manual

Welcome to the world of materials testing! If you are completely new to Universal Testing Machines (UTMs), don't worry. This manual will explain the basic concepts of what the machine does, what the numbers mean, and exactly how to use the software we have built.

---

## 1. What is a UTM?

A **Universal Testing Machine (UTM)** is an industrial machine used to test the physical strength of materials. The most common test is a **Tensile Test**. 

Imagine you are pulling a rubber band. You grab both ends and pull. As you pull, you feel resistance (Force/Load), and the rubber band gets longer (Extension). Eventually, if you pull hard enough, it snaps (Break/Peak). 


A UTM does exactly this, but with extreme precision, to industrial materials like metals, plastics, textiles, and wood. It uses mechanical grips to hold the sample, a motor to pull it apart at a constant speed, and sensors to measure exactly how much force it took to stretch and break it.

---

## 2. Understanding the Core Concepts

When you run a test, the software records and calculates 4 main physical properties:

### Load (Force)
- **What it is**: How much raw force the machine is pulling with.
- **Unit**: Kilonewtons (**kN**) or Newtons (**N**).
- **Analogy**: How heavy the weights you are lifting are.

### Extension (Displacement)
- **What it is**: How far the machine has stretched the material from its original starting point.
- **Unit**: Millimeters (**mm**).
- **Analogy**: How far the rubber band has stretched.

### Stress
- **What it is**: Load divided by the Area of the sample ($Stress = \frac{Load}{Area}$). 
- **Unit**: Megapascals (**MPa**).
- **Why it matters**: A thick steel bar takes more force to break than a thin steel wire. *Stress* levels the playing field by calculating the force *per square millimeter*. This allows you to compare the true strength of the material itself, regardless of how thick the sample is.

### Strain
- **What it is**: Extension divided by the original length of the sample ($Strain = \frac{Extension}{Original Length} \times 100$).
- **Unit**: Percentage (**%**).
- **Why it matters**: If a 100mm string stretches 10mm, that's a 10% strain. If a 10mm string stretches 10mm, that's a 100% strain. Strain tells you how stretchy a material is relative to its starting size.

---

## 3. How to Use the Software

### Step 1: Launch and Login
1. Open your terminal and run `python main.py`.
2. The **Login Screen** will appear.
3. **PC COMM Port**: Select the USB port your machine is plugged into. The software will remember this forever.
4. **Password**: Enter the default password (`admin`).
5. Click **START**.

### Step 2: Prepare the Test
Before clicking Start, you must tell the software about the sample you are testing so it can do the math correctly.
1. Fill in the **Operator, Customer, and Material** boxes for your records.
2. **CRITICAL STEP**: Measure your physical sample with calipers and type the **Width** and **Thickness** (in mm) into the boxes. 
3. Type in the **Gauge Length** (the distance between the two machine grips holding your sample).
> [!IMPORTANT]  
> If you do not enter the correct Width, Thickness, and Gauge Length, the software cannot calculate Stress and Strain correctly!

### Step 3: Run the Test
1. Click the large green **START TEST** button at the bottom.
2. The machine will begin pulling the sample.
3. The graph will immediately start drawing a curve. You can use the dropdowns above the graph to switch between looking at **Load vs Time**, **Stress vs Strain**, etc.
4. The big blue digital gauges will show you the exact numbers in real-time.
5. When the sample snaps, the machine will usually detect it and stop automatically (or you can press the red **STOP TEST** button).

### Step 4: Exporting Your Data
Once the test is stopped, you need to save it! Use the top **File** menu:
* **Save Current Test to DB**: Saves the test securely into the internal SQLite database.
* **Export to CSV**: Dumps every single data point to an Excel-friendly CSV file so you can analyze it later.
* **Reports -> Generate PDF**: Generates a beautiful, professional PDF document containing the graph, your company metadata, and the peak strength results to hand to your customer.

---

## 4. Understanding the Graph

When you look at a **Stress vs Strain** graph (or Load vs Extension), you will notice it usually has two distinct phases:

1. **The Straight Line (Elastic Region)**: At the beginning of the test, the line goes straight up diagonally. If you stop the test here, the material will snap back to its original shape exactly like a spring.
2. **The Curve (Plastic Region)**: The line will start to curve and flatten out. This means the material has permanently deformed (yielded). If you stop the test now, it will stay stretched out forever.
3. **The Peak**: The highest point on the graph. This is the **Ultimate Tensile Strength (UTS)** — the absolute maximum force the material could handle before it started tearing apart.

> [!TIP]
> If you don't have the machine connected yet, click **Machine -> Enable Mock Mode** in the top menu and press Start. The software will simulate a test so you can practice using the interface!
