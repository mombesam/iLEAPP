import polyline
from datetime import datetime
import warnings
import os

import folium
import fitdecode

from scripts.ilapfuncs import logfunc, tsv, open_sqlite_db_readonly, convert_ts_human_to_utc, convert_utc_human_to_timezone
from scripts.artifact_report import ArtifactHtmlReport


"""
General information
"""


__artifacts_v2__ = {
    "Strava": {
        "name": "Strava Artifacts",
        "description": "Extract all the data available related to Strava application (activities, athletes and routes)",
        "author": "@biancric - @EleRacca - @mombesam",
        "version": "0.1",
        "date": "2023-12-12",
        "requirements": "folium, fitdecode, xlsxwriter, and polyline",
        "category": "Strava",
        "notes": "",
        "paths": ('*/var/mobile/Containers/Data/Application/*/Library/Application Support/Strava.sqlite*', '*/var/mobile/Containers/Data/Application/*/Documents/FIT/Recordings*'),
        "function": "get_strava"
    }
}


"""
Set of functions to extract and manipulate artifacts from FIT files (credits to @fabian-nunes, on ALEAPP)
"""


# Function to create an HTML map from an encoded polyline (for activities extracted from Strava.sqlite)
def create_polyline(encoded_polyline, report_folder, activities_and_routes_counter, html_map, type):
    # Decode the polyline
    decoded_coordinates = polyline.decode(encoded_polyline)

    # Create a Folium map centered on the first coordinate in the decoded polyline
    map_center = decoded_coordinates[0]
    m = folium.Map(location=map_center, zoom_start=10, max_zoom=19)

    # Add a PolyLine (with Start and End markers) to the map using the decoded coordinates
    folium.PolyLine(locations=decoded_coordinates, color='red', weight=2.5, opacity=1).add_to(m)
    folium.Marker(location=decoded_coordinates[0], popup='Start Location',
                  icon=folium.Icon(color='blue', icon='flag', prefix='fa')).add_to(m)
    folium.Marker(location=decoded_coordinates[-1], popup='End Location',
                  icon=folium.Icon(color='red', icon='flag', prefix='fa')).add_to(m)

    # Save the map to an HTML file
    if type == "activities":
        title = f'Strava_Activity_db{activities_and_routes_counter}'
        if os.name == 'nt':
            m.save(f'{report_folder}\\{title}.html')
        else:
            m.save(f'{report_folder}/{title}.html')
        html_map.append(f'<iframe id="db_{activities_and_routes_counter}" src="Strava/{title}.html" width="100%"' 
                        f'height="500" class="map" hidden></iframe>')
    else:
        title = f'Strava_Activity_route{activities_and_routes_counter}'
        if os.name == 'nt':
            m.save(f'{report_folder}\\{title}.html')
        else:
            m.save(f'{report_folder}/{title}.html')
        html_map.append(f'<iframe id="route_{activities_and_routes_counter}" src="Strava/{title}.html" width="100%"'
                        f'height="500" class="map" hidden></iframe>')


def suppress_fitdecode_warnings(message, category, filename, lineno, file=None, line=None):
    if category == UserWarning and 'fitdecode' in message.args[0]:
        return
    else:
        return message, category, filename, lineno, file, line


# Set the filter function as the default warning filter
warnings.showwarning = suppress_fitdecode_warnings


# Function to export coordinates into KML file
def create_kml_file(counter, report_folder, coordinates):
    # save coords to a kml file
    kml = """
                        <?xml version="1.0" encoding="UTF-8"?>
                        <kml xmlns="http://www.opengis.net/kml/2.2">
                        <Document>
                        <name>Coordinates</name>
                        <description>Coordinates</description>
                        <Style id="yellowLineGreenPoly">
                            <LineStyle>
                                <color>7f00ffff</color>
                                <width>4</width>
                            </LineStyle>
                            <PolyStyle>
                                <color>7f00ff00</color>
                            </PolyStyle>
                        </Style>
                        <Placemark>
                            <name>Absolute Extruded</name>
                            <description>Transparent green wall with yellow outlines</description>
                            <styleUrl>#yellowLineGreenPoly</styleUrl>
                            <LineString>
                                <extrude>1</extrude>
                                <tessellate>1</tessellate>
                                <altitudeMode>clampedToGround</altitudeMode>
                                <coordinates>
                                """
    for coordinate in coordinates:
        kml += str(coordinate[1]) + "," + str(coordinate[0]) + ",0 \n"
    kml = kml[:-1]
    kml += """
                                </coordinates>
                            </LineString>
                        </Placemark>
                        </Document>
                        </kml>
                        """
    # remove the first space
    kml = kml[1:]
    # remove last line
    kml = kml[:-1]
    # remove extra indentation
    kml = kml.replace("    ", "")
    if os.name == 'nt':
        with open(report_folder + '\\' + str(counter) + '.kml', 'w') as f:
            f.write(kml)
            f.close()
    else:
        with open(report_folder + '/' + str(counter) + '.kml', 'w') as f:
            f.write(kml)
            f.close()


# Main function to extract traces from FIT files
def get_strava_fit(files_found, report_folder, timezone_offset):
    logfunc("Processing data for Strava FIT Files")
    data_list = []
    html_map = []
    act_fit = 1
    fit_files_found = [x for x in files_found if x.endswith('fit')]
    # file = str(fit_files_found[0])
    for file in fit_files_found:
        file = str(file)
        logfunc("Processing file: " + file)
        coordinates = []
        coordinatesE = []
        # Decode FIT file
        with fitdecode.FitReader(file) as fit:
            logfunc("Found Strava FIT file")
            for frame in fit:
                if frame.frame_type == fitdecode.FIT_FRAME_DATAMESG:
                    if frame.name == 'record':
                        # Check if the record message contains the position_lat
                        # and position_long fields.
                        if frame.has_field('position_lat') and frame.has_field('position_long'):
                            lat = frame.get_value('position_lat')
                            lon = frame.get_value('position_long')
                            timestamp = frame.get_value('timestamp')
                            timestamp = timestamp.timestamp()
                            # convert from UNIX timestamp to UTC
                            timestamp = datetime.utcfromtimestamp(timestamp)
                            timestamp = str(timestamp)
                            # convert from semicircles to degrees
                            lat = lat * (180.0 / 2 ** 31)
                            lon = lon * (180.0 / 2 ** 31)
                            # round to 5 decimal places
                            lat = round(lat, 5)
                            lon = round(lon, 5)
                            coordinates.append([lat, lon])
                            coordinatesE.append([lat, lon, timestamp])
                    elif frame.name == 'session':
                        if frame.has_field('total_elapsed_time'):
                            total_elapsed_time = frame.get_value('total_elapsed_time')
                            hours, remainder = divmod(total_elapsed_time, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            formatted_total_elapsed_time = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
                        if frame.has_field('start_time'):
                            start_time = frame.get_value('start_time')
                            # convert from FIT timestamp to UNIX timestamp
                            start_time_u = start_time.timestamp()
                            # add seconds to the UNIX timestamp
                            end_time = start_time_u + total_elapsed_time
                            # convert from UNIX timestamp to chosen timezone
                            start_time = datetime.utcfromtimestamp(start_time_u)
                            start_time = convert_ts_human_to_utc(str(start_time))
                            start_time = convert_utc_human_to_timezone(start_time, timezone_offset)
                            end_time = datetime.utcfromtimestamp(end_time)
                            end_time = convert_ts_human_to_utc(str(end_time))
                            end_time = convert_utc_human_to_timezone(end_time, timezone_offset)
                        if frame.has_field('sport'):
                            sport = frame.get_value('sport')
                        if frame.has_field('total_distance'):
                            total_distance = frame.get_value('total_distance')
                            # convert from m to km
                            total_distance = total_distance / 1000
                            total_distance = round(total_distance, 2)
        # Generate HTML file with the map and the route using Folium
        place_lat = []
        place_lon = []
        m = folium.Map(location=[coordinates[0][0], coordinates[0][1]], zoom_start=10, max_zoom=19)

        for coordinate in coordinates:
            # if points are too close, skip
            if len(place_lat) > 0 and abs(place_lat[-1] - coordinate[0]) < 0.0001 and abs(
                    place_lon[-1] - coordinate[1]) < 0.0001:
                continue
            else:
                place_lat.append(coordinate[0])
                place_lon.append(coordinate[1])

        points = []
        for i in range(len(place_lat)):
            points.append([place_lat[i], place_lon[i]])
            # Add points to map
            for index, lat in enumerate(place_lat):
                # Start point
                if index == 0:
                    folium.Marker([lat, place_lon[index]], popup=('Start Location\n'.format(index)),
                                  icon=folium.Icon(color='blue', icon='flag', prefix='fa')).add_to(m)
                # last point
                elif index == len(place_lat) - 1:
                    folium.Marker([lat, place_lon[index]], popup=(('End Location\n').format(index)),
                                  icon=folium.Icon(color='red', icon='flag', prefix='fa')).add_to(m)

        # Create polyline
        folium.PolyLine(points, color="red", weight=2.5, opacity=1).add_to(m)
        # Save the map to an HTML file
        title = 'Strava_Activity_fit' + str(act_fit)
        if os.name == 'nt':
            m.save(report_folder + '\\' + title + '.html')
        else:
            m.save(report_folder + '/' + title + '.html')
        html_map.append('<iframe id="fit_' + str(act_fit) + '" src="Strava/' + title + '.html" width="100%" height="500" class="map" hidden></iframe>')

        create_kml_file(f'fit_{act_fit}', report_folder, coordinates)

        data_list.append(
            (sport, start_time, end_time, formatted_total_elapsed_time, total_distance,
             f'<a href=Strava/fit_{act_fit}.kml class="badge badge-light" target="_blank">fit_{act_fit}.kml</a>',
             f'<button type="button" class="btn btn-light btn-sm" onclick="openMap(\'fit_{act_fit}\')">Show Map</button>')
        )
        act_fit += 1

    # Found one or more FIT files
    if len(fit_files_found) > 0:
        description = "Strava - Activities (FIT)"
        report = ArtifactHtmlReport(f'{description}')
        report.start_artifact_report(report_folder, f'{description}')
        report.add_script()

        # Filter out duplicate activites
        filter_no_duplicates = {activity[:-3]: 0 for activity in data_list}
        data_list_no_duplicates = []
        for activity in data_list:
            if filter_no_duplicates[activity[:-3]] == 0:
                data_list_no_duplicates.append(activity)
                filter_no_duplicates[activity[:-3]] = 1

        # Write data in report
        data_headers = ('Activity Type', 'Start Time', 'End Time', 'Total Time (hh:mm:ss)', 'Total Distance (km)',
                        'Coordinates KML', 'Map')
        report.write_artifact_data_table(data_headers, data_list_no_duplicates,
                                         '*/var/mobile/containers/data/application/*/Documents/Fit/*',
                                         html_escape=False, table_id='Strava Fit Files')

        # Add the maps to the report
        report.add_section_heading('Strava maps')
        for htmlMap in html_map:
            report.report_file.write(f'{htmlMap}')

        report.end_artifact_report()

        # Create TSV report
        tsvname = f'{description}'
        tsv(report_folder, data_headers, data_list_no_duplicates, tsvname)


"""
Set of functions to extract and manipulate artifacts from Strava.sqlite database
"""


# Function to execute a query on a database and retrieve the results (content and number of rows)
def db_fetch(db, query):
    cursor = db.cursor()
    cursor.execute(query)
    data = cursor.fetchall()
    return data, len(data)


# Main function to extract traces from Strava.sqlite
def get_strava_db(files_found, report_folder, timezone_offset):
    logfunc("Processing data for Strava activities, athletes, and routes")

    # Identify the Strava.sqlite file
    sqlite_files_found = [x for x in files_found if x.endswith('sqlite')]
    sqlite_db = None
    for file_found in sqlite_files_found:
        if str(file_found).endswith('Strava.sqlite'):
            sqlite_db = str(file_found)

    # If a Strava.sqlite database is found, extract the traces
    if sqlite_db is not None:
        db = open_sqlite_db_readonly(sqlite_db)

        # Query to extract information about activities performed by the user
        query_activities = f'''
                        SELECT 
                        ZACTIVITY.ZNAME as "Activity name",
                        ZACTIVITY.ZSPORTTYPE AS "Activity type",
                        ZACTIVITY.ZUSERDESCRIPTION AS "Description",
                        CASE WHEN ZACTIVITY.ZTRAINER THEN 'Yes' ELSE 'No' END "Static (indoors)",
                        datetime('2001-01-01', ZACTIVITY.ZSTARTTIMESTAMP || ' seconds') AS "Start time",
                        time(ZACTIVITY.ZELAPSEDTIME, 'unixepoch') AS "Total time (hh:mm:ss)",
                        time(ZACTIVITY.ZMOVINGTIME, 'unixepoch') AS "Moving time (hh:mm:ss)",
                        ROUND(ZACTIVITY.ZDISTANCE / 1000, 3) AS "Total distance (km)",
                        CASE ZACTIVITY.ZSHAREABLE WHEN NULL THEN NULL ELSE ZMAP.ZPOLYLINE END "Map polyline"
                        FROM ZACTIVITY
                        LEFT JOIN ZMAP ON ZACTIVITY.ZMAP = ZMAP.Z_PK
                        WHERE ZATHLETE = 1
                        ORDER BY ZACTIVITY.ZSTARTTIMESTAMP ASC'''
        data_list_activities, usagentries_activities = db_fetch(db, query_activities)

        # Query to extract information about the user and his friends
        query_user_and_friends = f'''
                        SELECT
                        CASE ZATHLETE.Z_PK WHEN 1 THEN "Main user" ELSE "Friend" END "User status",
                        ZATHLETE.ZFIRSTNAME AS "First name",
                        ZATHLETE.ZLASTNAME AS "Last name",
                        ZATHLETE.ZSEX || "/" || ZATHLETE.ZGENDER AS "Sex/Gender",
                        strftime('%Y-%m-%d', datetime('2001-01-01', ZATHLETE.ZDATEOFBIRTH || ' seconds')) AS "Date of birth",
                        ZATHLETE.ZLOCATIONCITY || ", " || ZATHLETE.ZLOCATIONSTATE AS "City and state",
                        ZATHLETE.ZEMAIL AS "Email address",
                        ZATHLETE.ZUSERNAME AS "Username",
                        datetime('2001-01-01', ZATHLETE.ZCREATEDAT || ' seconds') AS "Account creation date",
                        ZATHLETE.ZBIO AS "Bio",
                        ZATHLETE.ZIMAGELINKLARGE AS "Link to profile picture",
                        ZATHLETE.ZINSTAGRAMUSERNAME AS "Instagram username",
                        CASE WHEN ZATHLETE.ZPREMIUM THEN 'Yes' ELSE 'No' END "Premium"
                        FROM ZATHLETE
                        INNER JOIN ZATHLETEPROFILE ON ZATHLETE.ZREMOTEID = ZATHLETEPROFILE.ZREMOTEID
                        ORDER BY ZATHLETE.Z_PK ASC'''
        data_list_user_and_friends, usagentries_user_and_friends = db_fetch(db, query_user_and_friends)

        # Query to extract information about the routes created by the user
        query_routes = f'''
                        SELECT
                        ZROUTE.ZNAME AS "Route name",
                        ROUND(ZROUTE.ZDISTANCE / 1000, 3) AS "Distance (km)",
                        CASE ZROUTE.ZMAP WHEN NULL THEN NULL ELSE ZMAP.ZPOLYLINE END "Map polyline"
                        FROM ZROUTE
                        LEFT JOIN ZATHLETE ON ZATHLETE.Z_PK = ZROUTE.ZATHLETE
                        LEFT JOIN ZMAP ON ZMAP.Z_PK = ZROUTE.ZMAP
                        WHERE ZROUTE.ZNAME IS NOT NULL
                        ORDER BY ZROUTE.Z_PK ASC'''
        data_list_routes, usagentries_routes = db_fetch(db, query_routes)

        # One or more activities found
        if usagentries_activities > 0:
            descritpion = "Strava - Activities (Strava.sqlite)"
            report = ArtifactHtmlReport(f'{descritpion}')
            report.start_artifact_report(report_folder, f'{descritpion}')
            report.add_script()

            activities_counter = 1
            final_activities_list = []
            html_maps = []
            for activity in data_list_activities:
                activity_tmp = list(activity)
                # Check if a polyline is associated with the activity
                if activity[8] is not None:
                    # Create an HTML map with the polyline
                    create_polyline(activity[8], report_folder, activities_counter, html_maps, "activities")
                    create_kml_file(f'db_{activities_counter}', report_folder, polyline.decode(activity[8], 5))
                    # Remove the polyline from the final activity output, and add a button to show the map
                    del activity_tmp[8]
                    activity_tmp.append(f'<a href=Strava/db_{activities_counter}.kml class="badge badge-light" '
                                        f'target="_blank">db_{activities_counter}.kml</a>')
                    activity_tmp.append(f'<button type="button" class="btn btn-light btn-sm" '
                                        f'onclick="openMap(\'db_{activities_counter}\')">Show Map</button>')
                else:
                    # Remove the empty polyline from the final activity output
                    del activity_tmp[8]
                    activity_tmp.append(None)
                    activity_tmp.append(None)

                # Convert timestamps to chosen timezone
                start_time = convert_ts_human_to_utc(activity[4])
                start_time = convert_utc_human_to_timezone(start_time, timezone_offset)
                activity_tmp[4] = start_time

                final_activities_list.append(tuple(activity_tmp))
                activities_counter += 1

            # Write data in the report
            data_headers = ('Activity Name', 'Activity Type', 'Description', 'Static (indoors)', 'Start Time',
                            'Total time (hh:mm:ss)', 'Moving time (hh:mm:ss)', 'Total distance (km)', 'Coordinates KML',
                            'Map')
            report.write_artifact_data_table(data_headers, final_activities_list, sqlite_db, html_escape=False,
                                             table_id='Strava activities')

            # Add the maps to the report
            report.add_section_heading('Strava maps')
            for html_map in html_maps:
                report.report_file.write(f'{html_map}')

            report.end_artifact_report()

            # Create TSV report
            tsvname = f'{descritpion}'
            tsv(report_folder, data_headers, final_activities_list, tsvname)
        else:
            logfunc('Strava (activities) - No data available')

        # Information about user and/or friends found
        if usagentries_user_and_friends > 0:
            descritpion = "Strava - Athletes (Strava.sqlite)"
            report = ArtifactHtmlReport(f'{descritpion}')
            report.start_artifact_report(report_folder, f'{descritpion}')
            report.add_script()

            # Load the profile picture (if the analyst is connected to the network)
            data_list_user_and_friends_with_pictures = []
            for user in data_list_user_and_friends:
                    # Load the profile picture and add an HTML IMG element to the data list
                    user_tmp = list(user)
                    user_tmp[10] = f"<img src='{user_tmp[10]}' alt='{user_tmp[10]}' width='124px' length='124px'></mg>"
                    # Convert timestamps to chosen timezone
                    creation_time = convert_ts_human_to_utc(user[8])
                    creation_time = convert_utc_human_to_timezone(creation_time, timezone_offset)
                    user_tmp[8] = creation_time
                    data_list_user_and_friends_with_pictures.append(tuple(user_tmp))
            data_list_user_and_friends = data_list_user_and_friends_with_pictures

            # Write data in the report
            data_headers = ('User status', 'First name', 'Last name', 'Sex/Gender', 'Date of birth', 'City and State',
                            'Email address', 'Username', 'Account creation date', 'Biography', 'Profile picture',
                            'Instagram username', 'Premium account')
            report.write_artifact_data_table(data_headers, data_list_user_and_friends, sqlite_db, html_escape=False,
                                             table_id='Strava athletes')

            report.end_artifact_report()

            # Create TSV report
            tsvname = f'{descritpion}'
            tsv(report_folder, data_headers, data_list_user_and_friends, tsvname)
        else:
            logfunc('Strava (athletes) - No data available')

        # One or more routes found
        if usagentries_routes > 0:
            descritpion = "Strava - Routes (Strava.sqlite)"
            report = ArtifactHtmlReport(f'{descritpion}')
            report.start_artifact_report(report_folder, f'{descritpion}')
            report.add_script()

            routes_counter = 1
            final_routes_list = []
            html_maps = []
            for route in data_list_routes:
                route_tmp = list(route)
                # Check if a polyline is associated with the route
                if route[2] is not None:
                    # Create an HTML map with the polyline
                    create_polyline(route[2], report_folder, routes_counter, html_maps, "routes")
                    create_kml_file(f'route_{routes_counter}', report_folder, polyline.decode(route[2], 5))
                    # Remove the polyline from the final route output, and add a button to show the map
                    del route_tmp[2]
                    route_tmp.append(f'<a href=Strava/route_{routes_counter}.kml class="badge badge-light" '
                                        f'target="_blank">route_{routes_counter}.kml</a>')
                    route_tmp.append(f'<button type="button" class="btn btn-light btn-sm" '
                                     f'onclick="openMap(\'route_{routes_counter}\')">Show Map</button>')
                else:
                    # Remove the empty polyline from the final route output
                    del route_tmp[2]
                    route_tmp.append(None)
                    route_tmp.append(None)
                final_routes_list.append(tuple(route_tmp))
                routes_counter += 1

            # Write data in the report
            data_headers = ('Route name', 'Distance (km)', 'Coordinates KML', 'Map')
            report.write_artifact_data_table(data_headers, final_routes_list, sqlite_db, html_escape=False,
                                             table_id='Strava routes')

            # Add the maps to the report
            report.add_section_heading('Strava maps')
            for html_map in html_maps:
                report.report_file.write(f'{html_map}')

            report.end_artifact_report()

            # Create TSV report
            tsvname = f'{descritpion}'
            tsv(report_folder, data_headers, final_routes_list, tsvname)
        else:
            logfunc('Strava (routes) - No data available')

        db.close()

    else:
        logfunc('Strava - No data available')
        return


"""
Main function to extract Strava artifacts
"""


def get_strava(files_found, report_folder, seeker, wrap_text, time_offset):
    get_strava_fit(files_found, report_folder, time_offset)
    get_strava_db(files_found, report_folder, time_offset)
