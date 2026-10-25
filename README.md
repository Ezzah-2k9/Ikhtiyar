# Ikhtiyar: Smart Transport Choice for the UAE

Ikhtiyar (اختيار) means “choice.” It is a Python web application that helps users decide how to travel, not just where to go.

Navigation apps tell you how to reach a destination. Ikhtiyar brings cost, journey time and estimated carbon emissions together in one place, so you can compare transport options against your own priorities and the real-world conditions of travel in Dubai and the wider UAE.

## Features

- Compares six transport options: car, taxi, metro, bus, walking and cycling
- Interactive route map with Leaflet.js
- Personalised recommendations from a Random Forest model (scikit-learn)
- Live weather data from OpenWeather
- User accounts, a dashboard with saved trips and travel statistics, trip history export and privacy controls
- Deployed online on Render

## Tech stack

Python · Flask · scikit-learn · Pandas · NumPy · PostgreSQL · Gunicorn · HTML5 · CSS · JavaScript · Leaflet.js · Render

## Sustainability

Ikhtiyar supports UN SDG 11 (Sustainable Cities and Communities) and SDG 13 (Climate Action), and the UAE’s wider sustainability goals, by making the environmental cost of travel easier to see.

## Future vision

Integrating transport booking platforms, so users can go from comparing their options to booking their journey.

## Live demo

https://ikhtiyar-v2.onrender.com

## Team

Ramzia, Naureen and Ezzah Najmal, Grade 12A

## Environment setup

This project reads all secrets and API keys from environment variables. Do not commit real credentials to GitHub.

Create a `.env` file in the project root and add your own values:

```bash
SECRET_KEY=your_secret_key_here
LOCATIONIQ_KEY=your_locationiq_key_here
ORS_KEY=your_openrouteservice_key_here
TOMTOM_KEY=your_tomtom_api_key_here
GRAPHHOPPER_KEY=your_graphhopper_key_here
GEOAPIFY_KEY=your_geoapify_key_here
OPENWEATHER_KEY=your_openweather_key_here
DATABASE_URL=postgresql://username:password@host:port/database_name
