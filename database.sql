-- Create Database
CREATE DATABASE IF NOT EXISTS Cairo_Transportation;
USE Cairo_Transportation;

CREATE TABLE IF NOT EXISTS Neighborhoods_Districts (
    ID INT PRIMARY KEY,
    Name VARCHAR(255),
    Population INT,
    Type VARCHAR(50),
    X_coordinate DECIMAL(8,2),
    Y_coordinate DECIMAL(8,2)
);

CREATE TABLE IF NOT EXISTS Important_Facilities (
    ID VARCHAR(10) PRIMARY KEY,
    Name VARCHAR(255),
    Type VARCHAR(50),
    X_coordinate DECIMAL(8,2),
    Y_coordinate DECIMAL(8,2)
);

CREATE TABLE IF NOT EXISTS Existing_Roads (
    FromID VARCHAR(10),
    ToID VARCHAR(10),
    Distance_km DECIMAL(5,1),
    Current_Capacity INT,
    Coondition INT,
    PRIMARY KEY (FromID, ToID)
);

CREATE TABLE IF NOT EXISTS Potential_Roads (
    FromID VARCHAR(10),
    ToID VARCHAR(10),
    Distance_km DECIMAL(5,1),
    Estimated_Capacity INT,
    Construction_Cost INT,
    PRIMARY KEY (FromID, ToID)
);

CREATE TABLE IF NOT EXISTS Traffic_Flow (
    FromID VARCHAR(10),
    ToID VARCHAR(10),
    Morning_Peak INT,
    Afternoon INT,
    Evening_Peak INT,
    Night INT,
    PRIMARY KEY (FromID, ToID)
);

CREATE TABLE IF NOT EXISTS Metro_Lines (
    LineID VARCHAR(10) PRIMARY KEY,
    Name VARCHAR(255),
    Stations TEXT,
    Daily_Passengers INT
);

CREATE TABLE IF NOT EXISTS Bus_Routes (
    RouteID VARCHAR(10) PRIMARY KEY,
    Stops TEXT,
    Buses_Assigned INT,
    Daily_Passengers INT
);

CREATE TABLE IF NOT EXISTS Transportation_Demand (
    FromID VARCHAR(10),
    ToID VARCHAR(10),
    Daily_Passengers INT,
    PRIMARY KEY (FromID, ToID)
);

-- Insert Neighborhoods/Districts
INSERT INTO Neighborhoods_Districts VALUES
(1, 'Maadi', 250000, 'Residential', 31.25, 29.96),
(2, 'Nasr City', 500000, 'Mixed', 31.34, 30.06),
(3, 'Downtown Cairo', 100000, 'Business', 31.24, 30.04),
(4, 'New Cairo', 300000, 'Residential', 31.47, 30.03),
(5, 'Heliopolis', 200000, 'Mixed', 31.32, 30.09),
(6, 'Zamalek', 50000, 'Residential', 31.22, 30.06),
(7, '6th October City', 400000, 'Mixed', 30.98, 29.93),
(8, 'Giza', 550000, 'Mixed', 31.21, 29.99),
(9, 'Mohandessin', 180000, 'Business', 31.20, 30.05),
(10, 'Dokki', 220000, 'Mixed', 31.21, 30.03),
(11, 'Shubra', 450000, 'Residential', 31.24, 30.11),
(12, 'Helwan', 350000, 'Industrial', 31.33, 29.85),
(13, 'New Administrative Capital', 50000, 'Government', 31.80, 30.02),
(14, 'Al Rehab', 120000, 'Residential', 31.49, 30.06),
(15, 'Sheikh Zayed', 150000, 'Residential', 30.94, 30.01);

-- Insert Important Facilities
INSERT INTO Important_Facilities VALUES
('F1', 'Cairo International Airport', 'Airport', 31.41, 30.11),
('F2', 'Ramses Railway Station', 'Transit Hub', 31.25, 30.06),
('F3', 'Cairo University', 'Education', 31.21, 30.03),
('F4', 'Al-Azhar University', 'Education', 31.26, 30.05),
('F5', 'Egyptian Museum', 'Tourism', 31.23, 30.05),
('F6', 'Cairo International Stadium', 'Sports', 31.30, 30.07),
('F7', 'Smart Village', 'Business', 30.97, 30.07),
('F8', 'Cairo Festival City', 'Commercial', 31.40, 30.03),
('F9', 'Qasr El Aini Hospital', 'Medical', 31.23, 30.03),
('F10', 'Maadi Military Hospital', 'Medical', 31.25, 29.95);

-- Insert Existing Roads (Note: Using 'Coondition' as per your table definition)
INSERT INTO Existing_Roads VALUES
('1', '3', 8.5, 3000, 7),
('1', '8', 6.2, 2500, 6),
('2', '3', 5.9, 2800, 8),
('2', '5', 4.0, 3200, 9),
('3', '5', 6.1, 3500, 7),
('3', '6', 3.2, 2000, 8),
('3', '9', 4.5, 2600, 6),
('3', '10', 3.8, 2400, 7),
('4', '2', 15.2, 3800, 9),
('4', '14', 5.3, 3000, 10),
('5', '11', 7.9, 3100, 7),
('6', '9', 2.2, 1800, 8),
('7', '8', 24.5, 3500, 8),
('7', '15', 9.8, 3000, 9),
('8', '10', 3.3, 2200, 7),
('8', '12', 14.8, 2600, 5),
('9', '10', 2.1, 1900, 7),
('10', '11', 8.7, 2400, 6),
('11', 'F2', 3.6, 2200, 7),
('12', '1', 12.7, 2800, 6),
('13', '4', 45.0, 4000, 10),
('14', '13', 35.5, 3800, 9),
('15', '7', 9.8, 3000, 9),
('F1', '5', 7.5, 3500, 9),
('F1', '2', 9.2, 3200, 8),
('F2', '3', 2.5, 2000, 7),
('F7', '15', 8.3, 2800, 8),
('F8', '4', 6.1, 3000, 9);

-- Insert Potential Roads
INSERT INTO Potential_Roads VALUES
('1', '4', 22.8, 4000, 450),
('1', '14', 25.3, 3800, 500),
('2', '13', 48.2, 4500, 950),
('3', '13', 56.7, 4500, 1100),
('5', '4', 16.8, 3500, 320),
('6', '8', 7.5, 2500, 150),
('7', '13', 82.3, 4000, 1600),
('9', '11', 6.9, 2800, 140),
('10', 'F7', 27.4, 3200, 550),
('11', '13', 62.1, 4200, 1250),
('12', '14', 30.5, 3600, 610),
('14', '5', 18.2, 3300, 360),
('15', '9', 22.7, 3000, 450),
('F1', '13', 40.2, 4000, 800),
('F7', '9', 26.8, 3200, 540);

-- Insert Traffic Flow (Split RoadID into FromID/ToID)
INSERT INTO Traffic_Flow VALUES
('1', '3', 2800, 1500, 2600, 800),
('1', '8', 2200, 1200, 2100, 600),
('2', '3', 2700, 1400, 2500, 700),
('2', '5', 3000, 1600, 2800, 650),
('3', '5', 3200, 1700, 3100, 800),
('3', '6', 1800, 1400, 1900, 500),
('3', '9', 2400, 1300, 2200, 550),
('3', '10', 2300, 1200, 2100, 500),
('4', '2', 3600, 1800, 3300, 750),
('4', '14', 2800, 1600, 2600, 600),
('5', '11', 2900, 1500, 2700, 650),
('6', '9', 1700, 1300, 1800, 450),
('7', '8', 3200, 1700, 3000, 700),
('7', '15', 2800, 1500, 2600, 600),
('8', '10', 2000, 1100, 1900, 450),
('8', '12', 2400, 1300, 2200, 500),
('9', '10', 1800, 1200, 1700, 400),
('10', '11', 2200, 1300, 2100, 500),
('11', 'F2', 2100, 1200, 2000, 450),
('12', '1', 2600, 1400, 2400, 550),
('13', '4', 3800, 2000, 3500, 800),
('14', '13', 3600, 1900, 3300, 750),
('15', '7', 2800, 1500, 2600, 600),
('F1', '5', 3300, 2200, 3100, 1200),
('F1', '2', 3000, 2000, 2800, 1100),
('F2', '3', 1900, 1600, 1800, 900),
('F7', '15', 2600, 1500, 2400, 550),
('F8', '4', 2800, 1600, 2600, 600);

-- Insert Metro Lines
INSERT INTO Metro_Lines VALUES
('M1', 'Line 1 (Helwan-New Marg)', '12,1,3,F2,11', 1500000),
('M2', 'Line 2 (Shubra-Giza)', '11,F2,3,10,8', 1200000),
('M3', 'Line 3 (Airport-Imbaba)', 'F1,5,2,3,9', 800000);

-- Insert Bus Routes
INSERT INTO Bus_Routes VALUES
('B1', '1,3,6,9', 25, 35000),
('B2', '7,15,8,10,3', 30, 42000),
('B3', '2,5,F1', 20, 28000),
('B4', '4,14,2,3', 22, 31000),
('B5', '8,12,1', 18, 25000),
('B6', '11,5,2', 24, 33000),
('B7', '13,4,14', 15, 21000),
('B8', 'F7,15,7', 12, 17000),
('B9', '1,8,10,9,6', 28, 39000),
('B10', 'F8,4,2,5', 20, 28000);

-- Insert Transportation Demand
INSERT INTO Transportation_Demand VALUES
('3', '5', 15000),
('1', '3', 12000),
('2', '3', 18000),
('F2', '11', 25000),
('F1', '3', 20000),
('7', '3', 14000),
('4', '3', 16000),
('8', '3', 22000),
('3', '9', 13000),
('5', '2', 17000),
('11', '3', 24000),
('12', '3', 11000),
('1', '8', 9000),
('7', 'F7', 18000),
('4', 'F8', 12000),
('13', '3', 8000),
('14', '4', 7000);

