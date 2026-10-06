# -*- coding: utf-8 -*-
"""
Created on Thu Sep  3 09:32:35 2026

Bike-sharing analysis for planned special events in Washington, DC.

This script estimates event-related changes in Capital Bikeshare trips around
selected event venues by comparing event days with weekday-matched control days.
It calculates excess bike-sharing arrivals and departures within different
distances from the event venue and time windows relative to event start/end
times. A sensitivity analysis is performed for different station-selection
radii, and event-related bike-sharing shares are estimated relative to event
attendance.

Input:
    - Capital Bikeshare station-level trip data
    - Bike-sharing station locations
    - Planned special event information
    - Predefined venue- and weekday-specific control days

Output:
    - Event-level estimates of excess bike-sharing trips and bike-sharing shares
      for different temporal windows and station-selection radii.

@author: skoufas
"""

#%% USER INPUT

time_aggregation = '15min' #Set time aggregation unit. Better choice for higher-resolution results
event_name = 'Nationals Game' # 'Capitals Game', 'Wizards Game', 'Nationals Game'
#radius_around_venue = 1 # (in Km). Radius around venue I want to consider for estimating station tap-in/out differences, and therefore modal eemu
# I test diffent radii values within the for loop so I can have a sensitivity analysis

####################################################################################################################################################
#Venue selection based on the event_name
venue_names = {
    "Nationals Game": "Ballpark",
    "Capitals Game": "Capital One Arena",
    "Wizards Game": "Capital One Arena"
}

selected_venue_name = venue_names[event_name]

#%% FUNCTIONS

#Function for data preprocessing
def data_preprocessing(df):
    # 1. Convert everything to string to avoid mixed types
    df['time_bin'] = df['time_bin'].astype(str)
    # 2. Convert to timedelta
    df['time_bin'] = pd.to_timedelta(df['time_bin'], errors='coerce')
    # Convert timedelta → time
    df['time_bin'] = (df['time_bin'].apply(lambda td: (pd.Timestamp('2000-01-01') + td).time()))
    # Convert time_bin strings → datetime.time
    df['time_bin'] = pd.to_datetime(df['time_bin'],format="%H:%M:%S").dt.time
    df['time_bin_dt'] = (df['time_bin'].apply(lambda t: pd.Timestamp.combine(pd.Timestamp("2000-01-01"), t)))
    return df

# Function labeling the 2H time window in relation to the event start (0-2H, 2-4H, etc)
def label_event_2Htime(offset_hours, event_duration_hours):

    # BEFORE: count back from event start
    if offset_hours < 0:
        bin_2h = int(abs(offset_hours) // 2)
        start_h = bin_2h * 2
        end_h = start_h + 2
        return f'{start_h}h-{end_h}h before the game'

    # DURING: count forward from event start
    elif 0 <= offset_hours < event_duration_hours:
        bin_2h = int(offset_hours // 2)
        start_h = bin_2h * 2
        end_h = start_h + 2
        return f'{start_h}h-{end_h}h during the game'

    # AFTER: count forward from event END
    else:
        after_hours = offset_hours - event_duration_hours
        bin_2h = int(after_hours // 2)
        start_h = bin_2h * 2
        end_h = start_h + 2
        return f'{start_h}h-{end_h}h after the game'
    
# Function labeling the 15MIN time window in relation to the event start
def label_event_15MINtime(offset_hours, event_duration_hours):

    # BEFORE: count back from event start
    if offset_hours < 0:
        bin_15 = int(abs(offset_hours) / 0.25)
        start_min = bin_15 * 15
        end_min = start_min + 15
        return f'{start_min}min-{end_min}min before the game'

    # DURING: count forward from event start
    elif 0 <= offset_hours < event_duration_hours:
        bin_15 = int(offset_hours / 0.25)
        start_min = bin_15 * 15
        end_min = start_min + 15
        return f'{start_min}min-{end_min}min during the game'

    # AFTER: count forward from event END  ← THIS IS THE FIX
    else:
        after_hours = offset_hours - event_duration_hours
        bin_15 = int(after_hours / 0.25)
        start_min = bin_15 * 15
        end_min = start_min + 15
        return f'{start_min}min-{end_min}min after the game'

###############################################################################################################
###############################################################################################################
####################### ASSOCIATE EVENT VENUES WITH BIKESHARE STATIONS OF INTEREST ############################

#%% Import station names
os.chdir("...")
bikeshare_stations = gpd.read_file(".../bikeshare_stations.shp")

#Change CRS of stations so I can estimate distances
# EPSG:32618  # calculating distances in Washington DC, the most appropriate
bikeshare_stations = bikeshare_stations.to_crs("EPSG:32618")

#bikeshare_stations.dtypes

# Import coordinates of the venues
venue_locations = {
    "Ballpark": Point(-77.0075, 38.8730),
    "Capital One Arena": Point(-77.0209, 38.8982)
}

venues = gpd.GeoSeries(
    venue_locations,
    crs="EPSG:4326"
).to_crs("EPSG:32618")

#Estimate distances (in KM) of all stations to the two venues
bikeshare_stations["distance_Ballpark"] = (
    bikeshare_stations.geometry.distance(
        venues["Ballpark"]
    ) / 1000
)

bikeshare_stations["distance_Capital One Arena"] = (
    bikeshare_stations.geometry.distance(
        venues["Capital One Arena"]
    ) / 1000
)

###############################################################################################################
###############################################################################################################
####################### CONTROL DAYS - IMPORT THE DATA ON THE STOP LEVEL ######################################

os.chdir("...")
daynames = pd.read_csv('...')

#Import the venue-based control days
with open("XXXX.pkl", "rb") as f:
    control_days = pickle.load(f)

#Select the control days for the selected venue
selected_control_days = control_days[selected_venue_name]

# Convert control-day dictionary to:
# date -> weekday
control_date_to_weekday = {
    str(date): weekday
    for weekday, dates in selected_control_days.items()
    for date in dates
}

#Import only the control day data
os.chdir("...")

file_list = glob.glob("*.csv")   # all CSVs in the folder
control_days_arrivals_departures_list = []  # list to store dataframes

for file in file_list:
    # Extract the date part from the filename
    date_str = os.path.basename(file).eemu("_")[-1].replace(".csv", "")
    #print(file, " → extracted date:", date_str)
    #Check if this file belongs to the list of the control days
    if date_str in control_date_to_weekday:
        df = pd.read_csv(file)
        
        # Add control-day date
        df["CalendarDateKey"] = int(date_str)

        # Add weekday
        df["weekday"] = control_date_to_weekday[date_str]
        
        #Append to the control days df
        control_days_arrivals_departures_list.append(df)
        
    
#In the end merge them
control_days_arrivals_departures = pd.concat(control_days_arrivals_departures_list, ignore_index=True)

#Data preprocessing
control_days_arrivals_departures = data_preprocessing(control_days_arrivals_departures)

#Since control days have several days, estimate an average per station, time bin, direction, and WEEKDAY (so I can compare per WEEKDAY with the event days)
control_days_arrivals_departures = control_days_arrivals_departures.groupby(['stop_name', 'direction', 'time_bin_dt', 'weekday'])['number_of_trips'].mean().reset_index()
control_days_arrivals_departures['group'] = 'control'

#%%##############################################################################################################
###############################################################################################################
####################### EVENT DAYS - IMPORT THE DATA ON THE STOP LEVEL ########################################
# Import event data
events = pd.read_csv("...")

#add a month column
events['month'] = events['startdate'].str.eemu('-').str[1].astype(int)

# Convert the projected attendance to num
events['projectedattendance_num'] = pd.to_numeric(
    events['projectedattendance'],
    errors='coerce'
)
#event_name = 'Nationals Game'
# Find all the dates when this event took place during workdays of Spring 2024
event_dates_df = daynames.loc[(daynames['eventname']==event_name)
                          & (daynames["category"] == "workday")
                          & (daynames["month"].isin([3, 4, 5]))][['CalendarDateKey', 'weekday']]

event_dates = daynames.loc[(daynames['eventname']==event_name)
                          & (daynames["category"] == "workday")
                          & (daynames["month"].isin([3, 4, 5]))]['CalendarDateKey'].to_list()

# Estimate average attendance across all selected games in the game series
average_attendance = events.loc[(events['eventname']== event_name) & (events['start_CalendarDateKey'].isin(event_dates))]['projectedattendance_num'].mean()

modal_eemu_before_after_event = pd.DataFrame() #aggregated Bikeshare modal eemu accounting all bikeshare docks within the selected radius

# Loop over the dates of the game series
for event_date in event_dates:
    
    #print(event_date)

    # Weekday
    event_weekday = event_dates_df.loc[event_dates_df['CalendarDateKey']==event_date]['weekday'].iloc[0]
    
    # Find start time of the event and convert event start time to datetime
    event_start_time = events.loc[(events['eventname'] == event_name) & (events['start_CalendarDateKey'] == int(event_date))]['starttime'].iloc[0]
    event_start = pd.to_datetime("2000-01-01 " + event_start_time)
    
    # Find real duration (hours)
    event_real_duration = events.loc[(events['eventname'] == event_name) & (events['start_CalendarDateKey'] == int(event_date))]['real_time_duration'].iloc[0]
    
    # Find real event end
    event_end_time = (pd.to_datetime(event_start_time, format="%H:%M:%S")+ pd.Timedelta(hours=event_real_duration)).strftime("%H:%M:%S")
    event_end = event_start + pd.Timedelta(hours=event_real_duration) #New approach: Game start + real game duration
    
    # Find Event duration in hours
    event_duration_hours = (event_end - event_start).total_seconds() / 3600
        
    #FIND CRITICAL TIMES
    four_hour_before_start = event_start - pd.Timedelta(hours=4)
    two_hour_before_start = event_start - pd.Timedelta(hours=2)
    half_hour_before_end = event_end - pd.Timedelta(minutes=30) #New approach: Game end - 30minutes
    two_hour_after_end = event_end + pd.Timedelta(hours=2) #New approach: Game end + 2hours
    
    #FIND CRITICAL STANDARIZED TIME OFFETS -- ALL WILL BE CALCULATED BASED ON EVENT START TIME 
    # 4H BEFORE THE EVENT
    four_hour_before_end_offset_hours = (four_hour_before_start - event_start).total_seconds() / 3600
    # 2H BEFORE THE EVENT
    two_hour_before_end_offset_hours = (two_hour_before_start - event_start).total_seconds() / 3600
    # EVENT START TIME       : 0
    # 30MIN AFTER EVENT START: 0.25
    # 30MIN BEFORE EVENT END
    half_hour_before_end_offset_hours = (half_hour_before_end - event_start).total_seconds() / 3600
    # 2H AFTER THE EVENT END
    twohour_after_end_offset_hours = (two_hour_after_end - event_start).total_seconds() / 3600
    
    # Convert event start/end to relative timedeltas
    event_start_relative = event_start - event_start.normalize()
    event_end_relative = event_end - event_end.normalize()
    
    # Check that the investigation window stays within the same day (event start and 2h after the event end are in the same day)
    window_within_same_day = ((two_hour_after_end.date() == event_start.date()) | (two_hour_after_end.time() == pd.Timestamp("00:00:00").time()))
    
    #Find the attendance. If it does not exist, append an average attendance
    event_attendance = events.loc[(events['start_CalendarDateKey']==event_date) & (events['eventname']==event_name)]['projectedattendance'].iloc[0]
    # Convert to numeric safely
    event_attendance = pd.to_numeric(event_attendance, errors='coerce')
        
    if pd.notna(event_attendance):
        final_attendance = int(event_attendance)
    else:
        final_attendance = average_attendance

    #Import the arrivals and departures at the stop level for the event day
    os.chdir("...")
    event_date_str = str(event_date)
    filename = f"arrival_departure_rates_stop_{event_date_str}.csv"
    event_day_arrivals_departures = pd.read_csv(filename)

    #Data preprocessing
    #event day
    event_day_arrivals_departures = data_preprocessing(event_day_arrivals_departures)
    
    #Keep only columns I am interested in ('GRID_ID', 'time_bin_dt', 'direction', 'number_of_trips_event')
    event_day_arrivals_departures = event_day_arrivals_departures[['stop_name', 'time_bin_dt', 'direction', 'number_of_trips']]
     
    #BEFORE COMPARING CONTROL DAYS - EVENT DAYS check when the time window ends:
    #Category 1: If the two hour window after the game end is BEFORE midnight then I don't need to import the data of the next day
    #Category 2: If the two hour window after the game end is AFTER midnight then I NEED to import the data of the next day
    
    if window_within_same_day:
        # Category 1
        
        #Filter only with the control days I am interested based on the weekday
        selected_control_days_arrivals_departures = control_days_arrivals_departures.loc[control_days_arrivals_departures['weekday'] == event_weekday].copy()
        
        #Day 0
        selected_control_days_arrivals_departures['relative_time'] = selected_control_days_arrivals_departures['time_bin_dt'] - selected_control_days_arrivals_departures['time_bin_dt'].dt.normalize()
        event_day_arrivals_departures['relative_time'] = event_day_arrivals_departures['time_bin_dt'] - event_day_arrivals_departures['time_bin_dt'].dt.normalize()
        
        final_control_arrivals_departures = selected_control_days_arrivals_departures
             
        #Define the final event days
        final_event_arrivals_departures = event_day_arrivals_departures
        final_event_arrivals_departures['group'] = 'event'

    else:   
        # Category 2
        day_plus1 = int((pd.to_datetime(str(event_date), format='%Y%m%d') + pd.Timedelta(days=1)).strftime('%Y%m%d'))
        weekday_plus1 = pd.to_datetime(day_plus1, format="%Y%m%d").day_name()
        
        #Day 0 relative time
        event_day_arrivals_departures['relative_time'] = event_day_arrivals_departures['time_bin_dt'] - event_day_arrivals_departures['time_bin_dt'].dt.normalize()
            
        #Import data of the next day until the end of the time window
        #######################################################################
        # 2.1 EVENT DATA: Day after the event (e.g., if event is at 20230301, then import also data of 20230302)
             
        event_dateplus1_str = str(day_plus1)
        filename = f"arrival_departure_rates_stop_{event_dateplus1_str}.csv"
        event_dayplus1_arrivals_departures = pd.read_csv(filename)
             
        # Data preprocessing
        event_dayplus1_arrivals_departures = data_preprocessing(event_dayplus1_arrivals_departures)
             
        # Filter for the time window I am interested to (midnight till time window end)
        time_of_day = event_dayplus1_arrivals_departures['time_bin_dt'] - event_dayplus1_arrivals_departures['time_bin_dt'].dt.normalize()
        
        event_dayplus1_arrivals_departures = event_dayplus1_arrivals_departures[
            (time_of_day >= pd.Timedelta('00:00:00')) &
            (time_of_day < pd.Timedelta(two_hour_after_end.strftime("%H:%M:%S")))
        ].copy()
        
        #Day 1 relative time
        event_dayplus1_arrivals_departures['relative_time'] = (event_dayplus1_arrivals_departures['time_bin_dt'] - event_dayplus1_arrivals_departures['time_bin_dt'].dt.normalize()) + pd.Timedelta(days=1)
             
        # Keep only columns I am interested in
        event_dayplus1_arrivals_departures = event_dayplus1_arrivals_departures[['stop_name', 'time_bin_dt', 'relative_time', 'direction', 'number_of_trips']]
        event_dayplus1_arrivals_departures['weekday'] = weekday_plus1
        event_dayplus1_arrivals_departures['group'] = 'event'
             
        # Concatenate the event data of day, dayplus1
        final_event_arrivals_departures = pd.concat([event_day_arrivals_departures, event_dayplus1_arrivals_departures])
             
        #######################################################################
        # 2.2 CONTROL DATA: WeekDay after the one interested
             
        selected_control_days_arrivals_departures = control_days_arrivals_departures.loc[control_days_arrivals_departures['weekday'] == event_weekday].copy()
        
        #Day 0 relative time
        selected_control_days_arrivals_departures['relative_time'] = selected_control_days_arrivals_departures['time_bin_dt'] - selected_control_days_arrivals_departures['time_bin_dt'].dt.normalize()
             
        selected_control_daysplus1_arrivals_departures = control_days_arrivals_departures.loc[control_days_arrivals_departures['weekday'] == weekday_plus1].copy()
             
        # Filter for the time window I am interested to (midnight till time window end)
        time_of_day = selected_control_daysplus1_arrivals_departures["time_bin_dt"] - selected_control_daysplus1_arrivals_departures["time_bin_dt"].dt.normalize()
             
        selected_control_daysplus1_arrivals_departures = selected_control_daysplus1_arrivals_departures.loc[
            (time_of_day >= pd.Timedelta("00:00:00")) &
            (time_of_day < pd.Timedelta(two_hour_after_end.strftime("%H:%M:%S")))
        ].copy()
        
        #Day 1 relative time
        selected_control_daysplus1_arrivals_departures['relative_time'] = (selected_control_daysplus1_arrivals_departures['time_bin_dt'] - selected_control_daysplus1_arrivals_departures['time_bin_dt'].dt.normalize()) + pd.Timedelta(days=1)
                     
        # Keep only columns I am interested in
        selected_control_daysplus1_arrivals_departures = selected_control_daysplus1_arrivals_departures[['stop_name', 'time_bin_dt', 'relative_time', 'direction', 'number_of_trips']]
        selected_control_daysplus1_arrivals_departures['weekday'] = weekday_plus1
        selected_control_daysplus1_arrivals_departures['group'] = 'control'

             
        # Concatenate the control data of day, dayplus1
        final_control_arrivals_departures = pd.concat([selected_control_days_arrivals_departures, selected_control_daysplus1_arrivals_departures])
        
        #######################################################################
        #2.3 Groupby results in case there are duplicates
        
        #Final control data
        final_control_arrivals_departures = final_control_arrivals_departures.groupby(['stop_name', 'relative_time', 'direction', 'weekday'])['number_of_trips'].mean().reset_index()
        final_control_arrivals_departures['group'] = 'control'
        
        #Final event data
        final_event_arrivals_departures = final_event_arrivals_departures.groupby(['stop_name', 'relative_time', 'direction', 'weekday'])['number_of_trips'].mean().reset_index()
        final_event_arrivals_departures['group'] = 'event'
    
    #SENSITIVITY ANALYSIS -- ITERATE AMONG DIFFERENT RADIUS VALUES (IN KM)
    sensitivity_radius_values =  np.arange(1, 5.5, 0.5) # 1 to 5km with step 0.5
    
    # Create one dictionary for this event
    number_of_trips_diff_summary_dict = {
        'event_name': event_name,
        'event_date': event_date,
        'attendance': final_attendance,
        'event_start': event_start_time,
        'event_end': event_end_time
    }

    for radius_around_venue in sensitivity_radius_values:
        #print(radius_around_venue)
        #radius_around_venue = 1
        
        #Select all those stations around the selected venue based on the selected radius
        selected_bikeshare_stations = bikeshare_stations.loc[bikeshare_stations[f"distance_{selected_venue_name}"] <= radius_around_venue]
        
        #Concatenate with the control days dataframe ONLY FOR THE METRO STATIONS WE ARE INTERESTED IN
        comparison_arrival_departures = pd.concat([final_control_arrivals_departures.loc[final_control_arrivals_departures['stop_name'].isin(selected_bikeshare_stations['station_na'])], 
                                                   final_event_arrivals_departures.loc[final_event_arrivals_departures['stop_name'].isin(selected_bikeshare_stations['station_na'])]], 
                                                   ignore_index=True)
              
        # Offset relative to event start
        comparison_arrival_departures["event_offset_hours"] = (
            comparison_arrival_departures["relative_time"] - event_start_relative
        ).dt.total_seconds() / 3600
        
    
        arrival_departure_differences = comparison_arrival_departures.groupby(['stop_name', 'direction', 'group', 'event_offset_hours'])['number_of_trips'].sum().reset_index()
        
        #Pivot
        arrival_departure_differences_pivot = arrival_departure_differences.pivot_table(
            index=['stop_name', 'direction', 'event_offset_hours'],
            columns='group',
            values='number_of_trips',
            fill_value=0 
        ).reset_index()
        
        
        # Estimate differences
        arrival_departure_differences_pivot['number_of_trips_diff'] = arrival_departure_differences_pivot['event'] - arrival_departure_differences_pivot['control'] #absolute difference
        
        #%% NEW VERSION: USE THE 'event_offset_hours' instead Estimate the sums for both origins-destinations for different time window combinations
        
        # SUM OF POSITIVE DIFFERENCES IN TAP-OUTS - BEFORE THE GAME
        # 0-2H before
        number_of_trips_diff_2hbefore = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'destination') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(-1.75, -0.25)), "number_of_trips_diff"].sum()
        
        # 0-2H before + LATE ARRIVALS (0-0.25 during the game)
        number_of_trips_diff_2hbefore_05hduring = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'destination') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(-1.75, 0.25)), "number_of_trips_diff"].sum()
        
        # 0-4H before
        number_of_trips_diff_4hbefore = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'destination') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(-3.75, -0.25)), "number_of_trips_diff"].sum()
               
        # 0-4H before + LATE ARRIVALS (0-0.25 during the game)
        number_of_trips_diff_4hbefore_05hduring = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'destination') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(-3.75, 0.25)), "number_of_trips_diff"].sum()
        
        #######################################################################
        #######################################################################
        # SUM OF POSITIVE DIFFERENCES IN TAP-INS - AFTER THE GAME
        
        # 0.5H BEFORE THE END -- 2H AFTER THE GAME END
        number_of_trips_diff_05hbeforeend_2hafter = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'origin') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(half_hour_before_end_offset_hours, twohour_after_end_offset_hours)), "number_of_trips_diff"].sum()
       
        # 0-2H AFTER THE GAME END
        number_of_trips_diff_2hafter = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'origin') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(event_duration_hours, twohour_after_end_offset_hours)), "number_of_trips_diff"].sum()
            
        # WHOLE GAME + 2H AFTER THE GAME END
        number_of_trips_diff_during_2hafter = arrival_departure_differences_pivot.loc[
            (arrival_departure_differences_pivot['direction'] == 'origin') &
            (arrival_departure_differences_pivot['number_of_trips_diff'] > 0) &
            (arrival_departure_differences_pivot['event_offset_hours'].between(0, twohour_after_end_offset_hours)), "number_of_trips_diff"].sum()

        # --------------------------------------------------
        # SAVE RESULTS FOR THIS RADIUS
        # --------------------------------------------------

        radius_label = f"{radius_around_venue:g}"
        
        #######################################################################
        # BEFORE - DESTINATIONS
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_2hbefore_radius{radius_label}'
        ] = number_of_trips_diff_2hbefore
        
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_2hbefore_05hduring_radius{radius_label}'
        ] = number_of_trips_diff_2hbefore_05hduring
        
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_4hbefore_radius{radius_label}'
        ] = number_of_trips_diff_4hbefore
        
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_4hbefore_05hduring_radius{radius_label}'
        ] = number_of_trips_diff_4hbefore_05hduring
        
        #######################################################################
        # AFTER - ORIGINS
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_05hbeforeend_2hafter_radius{radius_label}'
        ] = number_of_trips_diff_05hbeforeend_2hafter
        
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_2hafter_radius{radius_label}'
        ] = number_of_trips_diff_2hafter
        
        number_of_trips_diff_summary_dict[
            f'number_of_trips_diff_during_2hafter_radius{radius_label}'
        ] = number_of_trips_diff_during_2hafter
        
        #######################################################################
        # Bikeshare EEMU - BEFORE
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_2hbefore_radius{radius_label}'
        ] = number_of_trips_diff_2hbefore / final_attendance * 100
        
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_2hbefore_05hduring_radius{radius_label}'
        ] = number_of_trips_diff_2hbefore_05hduring / final_attendance * 100
        
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_4hbefore_radius{radius_label}'
        ] = number_of_trips_diff_4hbefore / final_attendance * 100
        
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_4hbefore_05hduring_radius{radius_label}'
        ] = number_of_trips_diff_4hbefore_05hduring / final_attendance * 100
        
        #######################################################################
        # Bikeshare EEMU - AFTER
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_05hbeforeend_2hafter_radius{radius_label}'
        ] = number_of_trips_diff_05hbeforeend_2hafter / final_attendance * 100
        
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_2hafter_radius{radius_label}'
        ] = number_of_trips_diff_2hafter / final_attendance * 100
        
        number_of_trips_diff_summary_dict[
            f'bikeshare_eemu_during_2hafter_radius{radius_label}'
        ] = number_of_trips_diff_during_2hafter / final_attendance * 100
    # --------------------------------------------------
    # AFTER THE RADIUS LOOP
    # CREATE ONLY ONE ROW FOR THIS EVENT
    # --------------------------------------------------
    
    number_of_trips_diff_summary = pd.DataFrame([number_of_trips_diff_summary_dict])
    
    modal_eemu_before_after_event = pd.concat(
        [modal_eemu_before_after_event, number_of_trips_diff_summary],
        ignore_index=True
    )

# Export modal_eemu_file 
folder = "..."

modal_eemu_before_after_event.to_csv(
    f"{folder}\\bikeshare_eemu_before_after_{event_name}{time_aggregation}V2.csv",
    index=False
)
        
