# 24/7 Schedule Manager

A web application for managing 24/7 schedules for group homes, with support for multiple shifts and caregiver management.

## Features

- Caregiver Management (CRUD operations)
- Score-based scheduling limits
- Weekly schedule template
- Time off management
- Shift validation based on caregiver scores

## Shift Configuration

| Shift | Time | Color |
|-------|------|-------|
| A1 | 12am - 8am | Red |
| A2 | 4am - 12pm | Orange |
| A3 | 6am - 2pm | Yellow |
| G | 9am - 5pm | Green |
| B1 | 12pm - 8pm | Blue |
| B2 | 4pm - 12am | Indigo |
| B3 | 8pm - 4am | Violet |

## Caregiver Score Rules

- 80-100 points: Up to 40 hours/week
- 70-79 points: Up to 32 hours/week
- 60-69 points: Up to 24 hours/week
- Below 60 points: Not eligible for scheduling

## Setup

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Access the application at `http://localhost:5000`

## Data Storage

The application stores data in JSON files in the `data` directory:
- `caregivers.json`: Caregiver information
- `schedule_template.json`: Weekly schedule template
- `timeoff.json`: Time off requests

## API Endpoints

### Caregivers
- GET `/api/caregivers`: List all caregivers
- POST `/api/caregivers`: Add new caregiver
- DELETE `/api/caregivers/<id>`: Delete caregiver

### Schedule
- POST `/api/schedule`: Add caregiver to shift
- DELETE `/api/schedule`: Remove caregiver from shift

### Time Off
- POST `/api/timeoff`: Add time off request
- DELETE `/api/timeoff/<id>`: Delete time off request 