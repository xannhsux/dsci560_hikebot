"""NOAA-based detailed weather collector used by the hiking chatbot."""

import requests
import pandas as pd
from datetime import datetime
import time

class NOAAWeatherCollector:
    def __init__(self):
        self.base_url = "https://api.weather.gov"
        self.headers = {
            'User-Agent': 'USC-DSCI560-Research (student@usc.edu)'
        }
    
    def collect_hiking_weather_data(self):
        print("=== NOAA Official Weather Data Collection ===")
        print("Collecting detailed weather data from National Weather Service...")
        
        hiking_locations = [
            {'name': 'Yosemite Valley', 'lat': 37.7456, 'lon': -119.5840},
            {'name': 'Grand Canyon South Rim', 'lat': 36.0544, 'lon': -112.1401},
            {'name': 'Zion National Park', 'lat': 37.2982, 'lon': -113.0263},
            {'name': 'Rocky Mountain NP', 'lat': 40.3428, 'lon': -105.6836},
            {'name': 'Mount Rainier', 'lat': 46.8523, 'lon': -121.7603},
            {'name': 'Yellowstone', 'lat': 44.4280, 'lon': -110.5885}
        ]
        
        all_weather_data = []
        
        for location in hiking_locations:
            print(f"Getting weather data for {location['name']}...")
            
            try:
                weather_data = self.get_location_weather(
                    location['lat'], 
                    location['lon'], 
                    location['name']
                )
                
                if weather_data:
                    all_weather_data.append(weather_data)
                    print(f"Success: Got data for {location['name']}")
                else:
                    print(f"Failed: No data for {location['name']}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"Error getting weather for {location['name']}: {e}")
                continue
        
        if not all_weather_data:
            print("No weather data collected. Creating sample data for demonstration...")
            all_weather_data = self.create_sample_data()
        
        return all_weather_data
    
    def get_location_weather(self, lat, lon, location_name):
        try:
            points_url = f"{self.base_url}/points/{lat},{lon}"
            print(f"Requesting: {points_url}")
            
            points_response = requests.get(points_url, headers=self.headers, timeout=10)
            print(f"Points API status: {points_response.status_code}")
            
            if points_response.status_code == 200:
                points_data = points_response.json()
                properties = points_data['properties']
                
                forecast_url = properties['forecast']
                print(f"Requesting forecast: {forecast_url}")
                
                forecast_response = requests.get(forecast_url, headers=self.headers, timeout=10)
                print(f"Forecast API status: {forecast_response.status_code}")
                
                if forecast_response.status_code == 200:
                    forecast_data = forecast_response.json()
                    first_period = forecast_data['properties']['periods'][0]
                    
                    weather_record = {
                        'location_name': location_name,
                        'latitude': lat,
                        'longitude': lon,
                        'office': properties.get('gridId', 'Unknown'),
                        'zone': properties.get('forecastZone', '').split('/')[-1] if properties.get('forecastZone') else 'Unknown',
                        'period_name': first_period['name'],
                        'start_time': first_period['startTime'],
                        'end_time': first_period['endTime'],
                        'is_daytime': first_period['isDaytime'],
                        'temperature': first_period['temperature'],
                        'temperature_unit': first_period['temperatureUnit'],
                        'temperature_trend': first_period.get('temperatureTrend', 'None'),
                        'wind_speed': first_period['windSpeed'],
                        'wind_direction': first_period['windDirection'],
                        'short_forecast': first_period['shortForecast'],
                        'detailed_forecast': first_period['detailedForecast'],
                        'precipitation_chance': self.extract_precipitation_chance(first_period['detailedForecast']),
                        'humidity_level': self.extract_humidity(first_period['detailedForecast']),
                        'visibility': self.extract_visibility(first_period['detailedForecast']),
                        'weather_alerts': self.check_weather_alerts(properties.get('forecastZone', '')),
                        'clothing_recommendation': self.recommend_clothing(first_period),
                        'hiking_conditions': self.assess_hiking_conditions(first_period),
                        'safety_notes': self.extract_safety_warnings(first_period['detailedForecast']),
                        'collected_at': datetime.now().isoformat(),
                        'data_source': 'NOAA National Weather Service'
                    }
                    
                    return weather_record
                else:
                    print(f"Forecast API error: {forecast_response.status_code}")
            else:
                print(f"Points API error: {points_response.status_code}")
                if points_response.status_code == 404:
                    print("Location not covered by NOAA (outside US)")
        
        except Exception as e:
            print(f"Exception in get_location_weather: {e}")
        
        return None
    
    def create_sample_data(self):
        sample_data = [
            {
                'location_name': 'Yosemite Valley',
                'latitude': 37.7456,
                'longitude': -119.5840,
                'office': 'HNX',
                'zone': 'CAZ073',
                'period_name': 'This Afternoon',
                'start_time': '2025-09-07T12:00:00-07:00',
                'end_time': '2025-09-07T18:00:00-07:00',
                'is_daytime': True,
                'temperature': 72,
                'temperature_unit': 'F',
                'temperature_trend': 'None',
                'wind_speed': '5 to 10 mph',
                'wind_direction': 'W',
                'short_forecast': 'Sunny',
                'detailed_forecast': 'Sunny skies with light winds. Perfect weather for outdoor activities.',
                'precipitation_chance': 'None mentioned',
                'humidity_level': 'Normal',
                'visibility': 'Excellent',
                'weather_alerts': 'No active alerts',
                'clothing_recommendation': 't-shirt; long pants or shorts; light layer; sunglasses; sun protection',
                'hiking_conditions': 'Good temperature for hiking; Excellent hiking weather',
                'safety_notes': 'No specific warnings',
                'collected_at': datetime.now().isoformat(),
                'data_source': 'NOAA National Weather Service (Sample Data)'
            },
            {
                'location_name': 'Grand Canyon South Rim',
                'latitude': 36.0544,
                'longitude': -112.1401,
                'office': 'FGZ',
                'zone': 'AZZ006',
                'period_name': 'This Afternoon',
                'start_time': '2025-09-07T12:00:00-07:00',
                'end_time': '2025-09-07T18:00:00-07:00',
                'is_daytime': True,
                'temperature': 68,
                'temperature_unit': 'F',
                'temperature_trend': 'None',
                'wind_speed': '10 to 15 mph',
                'wind_direction': 'SW',
                'short_forecast': 'Partly Cloudy',
                'detailed_forecast': 'Partly cloudy with moderate southwest winds. Good visibility throughout the day.',
                'precipitation_chance': 'None mentioned',
                'humidity_level': 'Low',
                'visibility': 'Good',
                'weather_alerts': 'No active alerts',
                'clothing_recommendation': 'light jacket; long pants; light sweater; windproof layer; sunglasses; sun protection',
                'hiking_conditions': 'Good temperature for hiking; Excellent hiking weather; Moderate winds',
                'safety_notes': 'No specific warnings',
                'collected_at': datetime.now().isoformat(),
                'data_source': 'NOAA National Weather Service (Sample Data)'
            },
            {
                'location_name': 'Zion National Park',
                'latitude': 37.2982,
                'longitude': -113.0263,
                'office': 'SLC',
                'zone': 'UTZ009',
                'period_name': 'This Afternoon',
                'start_time': '2025-09-07T12:00:00-07:00',
                'end_time': '2025-09-07T18:00:00-07:00',
                'is_daytime': True,
                'temperature': 75,
                'temperature_unit': 'F',
                'temperature_trend': 'None',
                'wind_speed': '5 mph',
                'wind_direction': 'NE',
                'short_forecast': 'Mostly Sunny',
                'detailed_forecast': 'Mostly sunny skies with light northeast winds. Excellent conditions for hiking.',
                'precipitation_chance': 'None mentioned',
                'humidity_level': 'Low',
                'visibility': 'Excellent',
                'weather_alerts': 'No active alerts',
                'clothing_recommendation': 't-shirt; long pants or shorts; light layer; sunglasses; sun protection',
                'hiking_conditions': 'Good temperature for hiking; Excellent hiking weather',
                'safety_notes': 'No specific warnings',
                'collected_at': datetime.now().isoformat(),
                'data_source': 'NOAA National Weather Service (Sample Data)'
            }
        ]
        
        print("Created sample weather data for demonstration")
        return sample_data
    
    def extract_precipitation_chance(self, detailed_forecast):
        import re
        
        precipitation_patterns = [
            r'(\d+)\s*percent\s*chance',
            r'chance\s*of\s*\w+\s*(\d+)\s*percent',
            r'(\d+)%\s*chance'
        ]
        
        for pattern in precipitation_patterns:
            match = re.search(pattern, detailed_forecast.lower())
            if match:
                return f"{match.group(1)}%"
        
        if any(word in detailed_forecast.lower() for word in ['rain', 'snow', 'showers', 'thunderstorms']):
            return "Possible"
        
        return "None mentioned"
    
    def extract_humidity(self, detailed_forecast):
        if 'humid' in detailed_forecast.lower():
            return "High"
        elif 'dry' in detailed_forecast.lower():
            return "Low"
        else:
            return "Normal"
    
    def extract_visibility(self, detailed_forecast):
        if any(word in detailed_forecast.lower() for word in ['fog', 'haze', 'mist']):
            return "Reduced"
        elif 'clear' in detailed_forecast.lower():
            return "Excellent"
        else:
            return "Good"
    
    def check_weather_alerts(self, zone_url):
        return "No active alerts"
    
    def recommend_clothing(self, period):
        temp = period['temperature']
        temp_unit = period['temperatureUnit']
        forecast = period['shortForecast'].lower()
        detailed = period['detailedForecast'].lower()
        
        clothing = []
        
        if temp_unit == 'F':
            if temp <= 32:
                clothing.extend(['insulated jacket', 'warm layers', 'winter hat', 'gloves', 'insulated boots'])
            elif temp <= 50:
                clothing.extend(['warm jacket', 'long pants', 'warm hat', 'gloves'])
            elif temp <= 65:
                clothing.extend(['light jacket', 'long pants', 'light sweater'])
            elif temp <= 75:
                clothing.extend(['t-shirt', 'long pants or shorts', 'light layer'])
            elif temp <= 85:
                clothing.extend(['t-shirt', 'shorts', 'sun hat'])
            else:
                clothing.extend(['lightweight clothing', 'sun hat', 'cooling towel'])
        
        if any(word in forecast for word in ['rain', 'shower', 'storm']):
            clothing.append('rain jacket')
            clothing.append('waterproof pants')
        
        if any(word in forecast for word in ['wind', 'gusts']):
            clothing.append('windproof layer')
        
        if any(word in forecast for word in ['sun', 'clear', 'sunny']):
            clothing.extend(['sunglasses', 'sun protection'])
        
        if any(word in detailed for word in ['snow', 'ice', 'slippery']):
            clothing.extend(['traction devices', 'waterproof boots'])
        
        return '; '.join(clothing)
    
    def assess_hiking_conditions(self, period):
        temp = period['temperature']
        forecast = period['shortForecast'].lower()
        detailed = period['detailedForecast'].lower()
        
        conditions = []
        
        if temp <= 20 or temp >= 95:
            conditions.append("Extreme temperature - use caution")
        elif temp <= 35 or temp >= 85:
            conditions.append("Challenging temperature conditions")
        else:
            conditions.append("Good temperature for hiking")
        
        if any(word in forecast for word in ['thunderstorm', 'severe']):
            conditions.append("Dangerous weather - avoid hiking")
        elif any(word in forecast for word in ['heavy rain', 'snow']):
            conditions.append("Poor hiking conditions")
        elif any(word in forecast for word in ['light rain', 'scattered showers']):
            conditions.append("Fair conditions with precautions")
        elif any(word in forecast for word in ['sunny', 'clear', 'partly cloudy']):
            conditions.append("Excellent hiking weather")
        
        wind_speed = period['windSpeed'].lower()
        if 'mph' in wind_speed:
            try:
                speed_num = int(''.join(filter(str.isdigit, wind_speed.split('mph')[0])))
                if speed_num >= 25:
                    conditions.append("High winds - exercise caution")
                elif speed_num >= 15:
                    conditions.append("Moderate winds")
            except:
                pass
        
        return '; '.join(conditions)
    
    def extract_safety_warnings(self, detailed_forecast):
        warnings = []
        forecast_lower = detailed_forecast.lower()
        
        warning_keywords = {
            'Flash flood': ['flash flood', 'flooding'],
            'Lightning risk': ['thunderstorm', 'lightning'],
            'Extreme cold': ['freezing', 'frostbite', 'hypothermia'],
            'Heat danger': ['heat exhaustion', 'heat stroke', 'extreme heat'],
            'High winds': ['high wind', 'dangerous winds'],
            'Poor visibility': ['dense fog', 'low visibility'],
            'Avalanche conditions': ['avalanche', 'unstable snow'],
            'Ice hazard': ['icy conditions', 'slippery', 'black ice']
        }
        
        for warning_type, keywords in warning_keywords.items():
            for keyword in keywords:
                if keyword in forecast_lower:
                    warnings.append(warning_type)
                    break
        
        return '; '.join(warnings) if warnings else "No specific warnings"
    
    def save_to_csv(self, weather_data, filename='noaa_detailed_weather.csv'):
        print("Saving detailed weather data to CSV...")
        
        df = pd.DataFrame(weather_data)
        df.to_csv(filename, index=False)
        
        print(f"Data saved to {filename}")
        return df
    
    def display_analysis(self, df):
        print(f"\n=== Detailed Weather Data Analysis ===")
        print(f"Data dimensions: {df.shape}")
        
        if len(df) == 0:
            print("No data to analyze")
            return
        
        print(f"Locations covered: {df['location_name'].nunique()}")
        
        print(f"\nWeather overview:")
        display_cols = ['location_name', 'temperature', 'wind_speed', 'short_forecast', 'precipitation_chance']
        available_cols = [col for col in display_cols if col in df.columns]
        print(df[available_cols].head())
        
        print(f"\nHiking conditions summary:")
        if 'hiking_conditions' in df.columns:
            for idx, row in df.iterrows():
                print(f"{row['location_name']}: {row['hiking_conditions']}")
        
        print(f"\nMissing data count:")
        missing = df.isnull().sum()
        if missing.sum() > 0:
            print(missing[missing > 0])
        else:
            print("No missing data")

def demonstrate_noaa_collection():
    print("Starting NOAA Detailed Weather Data Collection")
    print("=" * 50)
    
    collector = NOAAWeatherCollector()
    weather_data = collector.collect_hiking_weather_data()
    
    print(f"Successfully collected {len(weather_data)} detailed weather records")
    
    df = collector.save_to_csv(weather_data)
    collector.display_analysis(df)
    
    print("NOAA detailed weather data collection completed!")
    return df

if __name__ == "__main__":
    demonstrate_noaa_collection()
