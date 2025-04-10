from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json
import os
from datetime import datetime, timedelta
import uuid
from collections import defaultdict
from google_calendar import export_schedule_to_calendar

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for flash messages

# Constants
SHIFTS = {
    'A1': {'time': '12am - 8am', 'color': 'R', 'hours': 8},
    'A2': {'time': '4am - 12pm', 'color': 'O', 'hours': 8},
    'A3': {'time': '6am - 2pm', 'color': 'Y', 'hours': 8},
    'G': {'time': '9am - 5pm', 'color': 'G', 'hours': 8},
    'B1': {'time': '12pm - 8pm', 'color': 'B', 'hours': 8},
    'B2': {'time': '4pm - 12am', 'color': 'I', 'hours': 8},
    'B3': {'time': '8pm - 4am', 'color': 'V', 'hours': 8}
}

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# Data storage paths
CAREGIVERS_FILE = 'data/caregivers.json'
SCHEDULE_TEMPLATE_FILE = 'data/schedule_template.json'
TIMEOFF_FILE = 'data/timeoff.json'
GENERATED_SCHEDULES_FILE = 'data/generated_schedules.json'

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

def load_data(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {}

def save_data(data, file_path):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def get_caregiver_hours_limit(score):
    if score >= 80:
        return 40
    elif score >= 70:
        return 32
    elif score >= 60:
        return 24
    return 0

def validate_caregiver_schedule(caregiver_id, day, shift):
    caregivers = load_data(CAREGIVERS_FILE)
    schedule = load_data(SCHEDULE_TEMPLATE_FILE)
    
    if caregiver_id not in caregivers:
        return False, "Caregiver not found"
    
    caregiver = caregivers[caregiver_id]
    score = caregiver['score']
    hours_limit = get_caregiver_hours_limit(score)
    
    if hours_limit == 0:
        return False, "Caregiver not eligible for scheduling"
    
    # Calculate current week's hours
    current_hours = 0
    for d in DAYS:
        for s in SHIFTS:
            if schedule.get(d, {}).get(s, []):
                if caregiver_id in schedule[d][s]:
                    current_hours += SHIFTS[s]['hours']
    
    if current_hours + SHIFTS[shift]['hours'] > hours_limit:
        return False, f"Exceeds weekly hours limit of {hours_limit}"
    
    # Check if already scheduled for this day
    if schedule.get(day, {}).get(shift, []):
        if caregiver_id in schedule[day][shift]:
            return False, "Already scheduled for this shift"
    
    return True, "Valid"

def generate_schedule_for_week(start_date, template, timeoff_data):
    weekly_schedule = {}
    current_date = start_date
    
    # Map weekday numbers to our day names
    day_map = {
        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
        4: 'Friday', 5: 'Saturday', 6: 'Sunday'
    }
    
    # Generate schedule for each day of the week
    for _ in range(7):
        date_str = current_date.strftime('%Y-%m-%d')
        template_day = day_map[current_date.weekday()]
        
        # Initialize the day's schedule from template
        weekly_schedule[date_str] = {}
        for shift, caregivers in template.get(template_day, {}).items():
            weekly_schedule[date_str][shift] = []
            
            # Check each caregiver for time off conflicts
            for caregiver_id in caregivers:
                has_timeoff = False
                for _, timeoff in timeoff_data.items():
                    if (timeoff['caregiver_id'] == caregiver_id and
                        timeoff['start_date'] <= date_str <= timeoff['end_date']):
                        has_timeoff = True
                        break
                
                if not has_timeoff:
                    weekly_schedule[date_str][shift].append(caregiver_id)
        
        current_date += timedelta(days=1)
    
    return weekly_schedule

@app.route('/')
def index():
    return render_template('index.html', shifts=SHIFTS)

@app.route('/caregivers')
def caregivers():
    caregivers_data = load_data(CAREGIVERS_FILE)
    return render_template('caregivers.html', caregivers=caregivers_data)

@app.route('/schedule')
def schedule():
    template = clean_schedule_template()
    caregivers_data = load_data(CAREGIVERS_FILE)
    return render_template('schedule.html', shifts=SHIFTS, days=DAYS, template=template, caregivers=caregivers_data)

@app.route('/timeoff')
def timeoff():
    timeoff_data = load_data(TIMEOFF_FILE)
    caregivers_data = load_data(CAREGIVERS_FILE)
    
    # Add caregiver names to timeoff data
    for id, to in timeoff_data.items():
        if to['caregiver_id'] in caregivers_data:
            to['caregiver_name'] = caregivers_data[to['caregiver_id']]['name']
    
    return render_template('timeoff.html', timeoff=timeoff_data)

@app.route('/generate_schedule', methods=['GET', 'POST'])
def generate_schedule():
    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d')
        num_weeks = int(request.form['num_weeks'])
        
        template = load_data(SCHEDULE_TEMPLATE_FILE)
        timeoff_data = load_data(TIMEOFF_FILE)
        caregivers_data = load_data(CAREGIVERS_FILE)
        
        generated_schedules = []
        current_date = start_date
        
        for week in range(num_weeks):
            weekly_schedule = generate_schedule_for_week(current_date, template, timeoff_data)
            generated_schedules.append({
                'week_start': current_date.strftime('%Y-%m-%d'),
                'schedule': weekly_schedule
            })
            current_date += timedelta(days=7)

        # Save the generated schedule
        saved_schedules = load_data(GENERATED_SCHEDULES_FILE)
        schedule_id = str(uuid.uuid4())
        saved_schedules[schedule_id] = {
            'id': schedule_id,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'num_weeks': num_weeks,
            'schedules': generated_schedules
        }
        save_data(saved_schedules, GENERATED_SCHEDULES_FILE)
        
        return render_template(
            'generated_schedule.html',
            schedules=generated_schedules,
            shifts=SHIFTS,
            caregivers=caregivers_data,
            schedule_id=schedule_id
        )
    
    return render_template('generate_schedule.html')

def get_caregiver_schedule_summary(schedule_data, caregivers):
    summary = defaultdict(lambda: {
        'shifts': [],
        'total_hours': 0,
        'shifts_by_week': defaultdict(int),
        'timeoff': []
    })
    
    timeoff_data = load_data(TIMEOFF_FILE)
    
    for week in schedule_data['schedules']:
        week_start = datetime.strptime(week['week_start'], '%Y-%m-%d')
        week_end = week_start + timedelta(days=6)
        week_str = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
        
        for day_idx, day in enumerate(DAYS):
            current_date = week_start + timedelta(days=day_idx)
            day_str = current_date.strftime('%Y-%m-%d')
            
            if day_str in week['schedule']:
                for shift, caregiver_ids in week['schedule'][day_str].items():
                    for caregiver_id in caregiver_ids:
                        if caregiver_id:
                            shift_info = SHIFTS[shift]
                            summary[caregiver_id]['shifts'].append({
                                'date': day_str,
                                'day': day,
                                'shift': shift,
                                'shift_time': shift_info['time'],
                                'hours': shift_info['hours']
                            })
                            summary[caregiver_id]['total_hours'] += shift_info['hours']
                            summary[caregiver_id]['shifts_by_week'][week_str] += shift_info['hours']
    
    # Add time off information
    for timeoff_id, timeoff in timeoff_data.items():
        caregiver_id = timeoff['caregiver_id']
        if caregiver_id in summary:
            summary[caregiver_id]['timeoff'].append({
                'start_date': timeoff['start_date'],
                'end_date': timeoff['end_date'],
                'status': timeoff['status']
            })
    
    # Convert to a more readable format
    formatted_summary = []
    for caregiver_id, data in summary.items():
        if caregiver_id in caregivers:
            caregiver = caregivers[caregiver_id]
            formatted_summary.append({
                'caregiver_name': caregiver['name'],
                'caregiver_id': caregiver_id,
                'shifts': sorted(data['shifts'], key=lambda x: x['date']),
                'total_hours': data['total_hours'],
                'shifts_by_week': dict(sorted(data['shifts_by_week'].items())),
                'timeoff': sorted(data['timeoff'], key=lambda x: x['start_date']),
                'score': caregiver.get('score', 0),
                'hours_limit': get_caregiver_hours_limit(caregiver.get('score', 0))
            })
    
    return sorted(formatted_summary, key=lambda x: x['caregiver_name'])

def get_shift_schedule_summary(schedule_data):
    summary = {shift_id: {
        'shifts': [],
        'total_assignments': 0,
        'assignments_by_week': defaultdict(int),
        'caregivers': defaultdict(int)
    } for shift_id in SHIFTS}
    
    for week in schedule_data['schedules']:
        week_start = datetime.strptime(week['week_start'], '%Y-%m-%d')
        week_end = week_start + timedelta(days=6)
        week_str = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
        
        for day_idx, day in enumerate(DAYS):
            current_date = week_start + timedelta(days=day_idx)
            day_str = current_date.strftime('%Y-%m-%d')
            
            if day_str in week['schedule']:
                for shift_id, caregiver_ids in week['schedule'][day_str].items():
                    if caregiver_ids:
                        summary[shift_id]['shifts'].append({
                            'date': day_str,
                            'day': day,
                            'caregivers': caregiver_ids
                        })
                        summary[shift_id]['total_assignments'] += len(caregiver_ids)
                        summary[shift_id]['assignments_by_week'][week_str] += len(caregiver_ids)
                        
                        for caregiver_id in caregiver_ids:
                            summary[shift_id]['caregivers'][caregiver_id] += 1
    
    # Add shift information
    for shift_id in summary:
        summary[shift_id]['time'] = SHIFTS[shift_id]['time']
        summary[shift_id]['hours'] = SHIFTS[shift_id]['hours']
        summary[shift_id]['shifts'] = sorted(summary[shift_id]['shifts'], key=lambda x: x['date'])
        summary[shift_id]['assignments_by_week'] = dict(sorted(summary[shift_id]['assignments_by_week'].items()))
    
    return summary

@app.route('/view_schedules')
def view_schedules():
    saved_schedules = load_data(GENERATED_SCHEDULES_FILE)
    # Sort schedules by creation date, newest first
    sorted_schedules = sorted(
        saved_schedules.values(),
        key=lambda x: x['created_at'],
        reverse=True
    )
    view_type = request.args.get('view', 'list')
    return render_template(
        'view_schedules.html',
        saved_schedules=sorted_schedules,
        view_type=view_type
    )

@app.route('/view_schedule/<schedule_id>')
def view_schedule(schedule_id):
    schedules = load_data(GENERATED_SCHEDULES_FILE)
    caregivers = load_data(CAREGIVERS_FILE)
    
    if schedule_id not in schedules:
        flash('Schedule not found', 'error')
        return redirect(url_for('view_schedules'))
    
    schedule_data = schedules[schedule_id]
    view_type = request.args.get('view', 'calendar')
    
    # Get the first week's start date from schedules array
    if schedule_data['schedules'] and len(schedule_data['schedules']) > 0:
        week_start = datetime.strptime(schedule_data['schedules'][0]['week_start'], '%Y-%m-%d')
    else:
        week_start = datetime.strptime(schedule_data['start_date'], '%Y-%m-%d')
    
    # Common template variables
    template_vars = {
        'schedule': schedule_data,
        'caregivers': caregivers,
        'shifts': SHIFTS,
        'created_at': schedule_data['created_at'],
        'view': view_type,  # Add current view type
    }
    
    if view_type == 'caregiver':
        caregiver_summary = get_caregiver_schedule_summary(schedule_data, caregivers)
        template_vars.update({
            'caregiver_summary': caregiver_summary,
        })
        return render_template('schedule_views/caregiver_view.html', **template_vars)
    
    elif view_type == 'shift':
        shift_summary = get_shift_schedule_summary(schedule_data)
        template_vars.update({
            'shift_summary': shift_summary,
        })
        return render_template('schedule_views/shift_view.html', **template_vars)
    
    elif view_type == 'hour':
        return render_template('schedule_views/hour_view.html', **template_vars)
    
    # Default calendar view
    template_vars.update({
        'days': DAYS,
        'week_start': week_start,
        'export_button': True
    })
    return render_template('view_schedule.html', **template_vars)

@app.route('/api/schedules/<schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    saved_schedules = load_data(GENERATED_SCHEDULES_FILE)
    if schedule_id in saved_schedules:
        del saved_schedules[schedule_id]
        save_data(saved_schedules, GENERATED_SCHEDULES_FILE)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Schedule not found'}), 404

# API Endpoints
@app.route('/api/caregivers', methods=['GET', 'POST'])
def api_caregivers():
    if request.method == 'GET':
        return jsonify(load_data(CAREGIVERS_FILE))
    
    data = request.json
    caregivers = load_data(CAREGIVERS_FILE)
    caregiver_id = str(uuid.uuid4())
    
    caregivers[caregiver_id] = {
        'name': data['name'],
        'score': data['score']
    }
    
    save_data(caregivers, CAREGIVERS_FILE)
    return jsonify({'id': caregiver_id})

@app.route('/api/caregivers/<id>', methods=['PUT', 'DELETE'])
def api_caregiver(id):
    caregivers = load_data(CAREGIVERS_FILE)
    if id not in caregivers:
        return jsonify({'status': 'error', 'message': 'Caregiver not found'}), 404

    if request.method == 'DELETE':
        del caregivers[id]
        save_data(caregivers, CAREGIVERS_FILE)
        return jsonify({'status': 'success'})
    
    elif request.method == 'PUT':
        data = request.json
        if 'name' not in data or 'score' not in data:
            return jsonify({'status': 'error', 'message': 'Name and score are required'}), 400
        
        caregivers[id].update({
            'name': data['name'],
            'score': data['score']
        })
        save_data(caregivers, CAREGIVERS_FILE)
        return jsonify({'status': 'success'})

@app.route('/api/schedule', methods=['POST', 'DELETE'])
def api_schedule():
    data = request.json
    schedule = load_data(SCHEDULE_TEMPLATE_FILE)
    
    if request.method == 'POST':
        is_valid, message = validate_caregiver_schedule(
            data['caregiver_id'],
            data['day'],
            data['shift']
        )
        
        if not is_valid:
            return jsonify({'status': 'error', 'message': message}), 400
        
        if data['day'] not in schedule:
            schedule[data['day']] = {}
        if data['shift'] not in schedule[data['day']]:
            schedule[data['day']][data['shift']] = []
        
        schedule[data['day']][data['shift']].append(data['caregiver_id'])
        save_data(schedule, SCHEDULE_TEMPLATE_FILE)
        return jsonify({'status': 'success'})
    
    elif request.method == 'DELETE':
        if (data['day'] in schedule and 
            data['shift'] in schedule[data['day']] and 
            data['caregiver_id'] in schedule[data['day']][data['shift']]):
            schedule[data['day']][data['shift']].remove(data['caregiver_id'])
            save_data(schedule, SCHEDULE_TEMPLATE_FILE)
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Schedule entry not found'}), 404

@app.route('/api/timeoff', methods=['POST'])
def api_timeoff():
    data = request.json
    timeoff = load_data(TIMEOFF_FILE)
    timeoff_id = str(uuid.uuid4())
    
    timeoff[timeoff_id] = {
        'caregiver_id': data['caregiver_id'],
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'status': 'pending'
    }
    
    save_data(timeoff, TIMEOFF_FILE)
    return jsonify({'id': timeoff_id})

@app.route('/api/timeoff/<id>', methods=['DELETE'])
def api_delete_timeoff(id):
    timeoff = load_data(TIMEOFF_FILE)
    if id in timeoff:
        del timeoff[id]
        save_data(timeoff, TIMEOFF_FILE)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Time off request not found'}), 404

@app.route('/api/caregivers/<id>/initials', methods=['PUT'])
def update_caregiver_initials(id):
    data = request.json
    caregivers = load_data(CAREGIVERS_FILE)
    
    if id not in caregivers:
        return jsonify({'status': 'error', 'message': 'Caregiver not found'}), 404
    
    initials = data.get('initials', '').strip().upper()
    if len(initials) > 3:
        return jsonify({'status': 'error', 'message': 'Initials must be 3 characters or less'}), 400
    
    caregivers[id]['initials'] = initials
    save_data(caregivers, CAREGIVERS_FILE)
    return jsonify({'status': 'success'})

def clean_schedule_template():
    schedule = load_data(SCHEDULE_TEMPLATE_FILE)
    caregivers = load_data(CAREGIVERS_FILE)
    cleaned = False
    
    for day in DAYS:
        if day in schedule:
            for shift in SHIFTS:
                if shift in schedule[day]:
                    # Filter out non-existent caregiver IDs
                    valid_caregivers = [c for c in schedule[day][shift] if c in caregivers]
                    if len(valid_caregivers) != len(schedule[day][shift]):
                        schedule[day][shift] = valid_caregivers
                        cleaned = True
    
    if cleaned:
        save_data(schedule, SCHEDULE_TEMPLATE_FILE)
    return schedule

@app.route('/export_to_calendar/<schedule_id>')
def export_to_calendar(schedule_id):
    """Export a schedule to Google Calendar."""
    schedules = load_data(GENERATED_SCHEDULES_FILE)
    caregivers = load_data(CAREGIVERS_FILE)
    
    if schedule_id not in schedules:
        flash('Schedule not found', 'error')
        return redirect(url_for('view_schedules'))
    
    schedule_data = schedules[schedule_id]
    
    # Time conversion helper
    def parse_time(time_str, base_date, is_end_time=False):
        """Convert time string to datetime, handling overnight shifts."""
        time = time_str.lower().strip()
        is_pm = 'pm' in time
        time = time.replace('am', '').replace('pm', '').strip()
        
        # Convert hour to 24-hour format
        if time == '12':
            if is_pm:  # 12pm = 12:00
                hour = 12
                minute = 0
            else:      # 12am = 00:01 for start time, 00:00 for end time
                hour = 0
                minute = 1 if not is_end_time else 0
        else:
            hour = int(time)
            if is_pm and hour != 12:
                hour += 12
            minute = 0
        
        # Create datetime object
        result = base_date.replace(hour=hour, minute=minute, second=0)
        
        # Handle overnight shifts by checking if end time is earlier than start time
        if is_end_time:
            # For shifts ending at early morning hours (1am-11am)
            if (hour >= 0 and hour < 12) and not is_pm:
                result += timedelta(days=1)
        
        return result
    
    # Process each week in the schedule
    for week_schedule in schedule_data['schedules']:
        week_start = datetime.strptime(week_schedule['week_start'], '%Y-%m-%d')
        
        # Create events for each day in the schedule
        for day_idx, day in enumerate(DAYS):
            current_date = week_start + timedelta(days=day_idx)
            day_str = current_date.strftime('%Y-%m-%d')
            
            if day_str in week_schedule['schedule']:
                for shift, caregiver_ids in week_schedule['schedule'][day_str].items():
                    for caregiver_id in caregiver_ids:
                        if caregiver_id:
                            caregiver = caregivers.get(caregiver_id, {})
                            shift_info = SHIFTS[shift]
                            shift_times = shift_info['time'].split(' - ')
                            
                            # Parse shift times
                            start_time = parse_time(shift_times[0], current_date, False)
                            end_time = parse_time(shift_times[1], current_date, True)
                            
                            # Verify 8-hour duration
                            duration = (end_time - start_time).total_seconds() / 3600
                            if duration != 8:
                                # Adjust end time if duration is not 8 hours
                                end_time = start_time + timedelta(hours=8)
                            
                            # Create schedule entry for calendar with timezone
                            schedule_entry = {
                                'caregiver_name': caregiver.get('name', 'Unknown Caregiver'),
                                'client_name': 'Awaaz247',
                                'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'notes': f"{shift_info['time']} PST",
                                'timezone': 'America/Los_Angeles'
                            }
                            
                            # Export to Google Calendar
                            event_link = export_schedule_to_calendar(schedule_entry)
                            if event_link:
                                flash(f'Successfully exported {day} {shift} to Google Calendar', 'success')
                            else:
                                flash(f'Failed to export {day} {shift} to Google Calendar', 'error')
    
    return redirect(url_for('view_schedule', schedule_id=schedule_id))

# Custom Jinja filter for day offset
@app.template_filter('day_offset')
def day_offset(day):
    return timedelta(days=DAYS.index(day))

if __name__ == '__main__':
    # Use environment variables for host and port
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 