// static/js/map_config.js
// Global map-related variables and Leaflet configurations

let map; // Leaflet map instance
let userLocationMarker = null;
let accuracyCircle = null;
let currentRoutePolyline = null;
let destinationMarkerLeaflet = null; // Renamed to avoid conflict if you have another `destinationMarker`

// Layer groups for filtering markers by status
const markerLayers = {
    open: L.layerGroup(),
    closed: L.layerGroup(),
    sever_traffic_jam: L.layerGroup(),
    unknown: L.layerGroup()
};

// Store L.Marker objects keyed by fence.id for easy access
const checkpointMarkers = {};

// Icon definitions for markers
const icons = {
    open: L.divIcon({
        html: `<div style="background-color: var(--success-color); width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.5);"></div>`, // Visual size: 16x16 dot
        className: 'leaflet-div-icon-custom checkpoint-marker-wrapper',
        iconSize: [24, 24], // Clickable area: 24x24
        iconAnchor: [12, 12]  // Anchor point in the middle of the clickable area
    }),
    closed: L.divIcon({
        html: `<div style="background-color: var(--danger-color); width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.5);"></div>`,
        className: 'leaflet-div-icon-custom checkpoint-marker-wrapper',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    }),
    sever_traffic_jam: L.divIcon({
        html: `<div style="background-color: var(--warning-color); width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.5);"></div>`,
        className: 'leaflet-div-icon-custom checkpoint-marker-wrapper',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    }),
    unknown: L.divIcon({
        html: `<div style="background-color: var(--unknown-color); width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.5);"></div>`,
        className: 'leaflet-div-icon-custom checkpoint-marker-wrapper',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    }),
    userLocation: L.divIcon({
        html: `<div class="user-location-pulse" style="background-color: var(--primary-color); width: 20px; height: 20px; border: 3px solid white;"></div>`, // Visual size: 20x20 dot
        className: 'leaflet-div-icon-custom user-marker-wrapper',
        iconSize: [30, 30], // Clickable area: 30x30
        iconAnchor: [15, 15] // Centered
    }),
    destination: L.divIcon({
        html: `<div style="background-color: var(--accent-color); width:20px; height:20px; border-radius:50%; border:2px solid white; box-shadow: 0 1px 2px rgba(0,0,0,0.3);"></div>`, // Visual size: 16x16 dot
        className: 'leaflet-div-icon-custom destination-marker-wrapper',
        iconSize: [24, 24], // Clickable area
        iconAnchor: [12, 24] // Anchor at bottom-center of clickable area
    })
};

// Styles and labels for different statuses (used for popups, lists, etc.)
const statusDetails = {
    open: { color: 'var(--success-color)', icon: 'fa-check-circle', label: 'مفتوح', headerColor: 'var(--success-color)' },
    closed: { color: 'var(--danger-color)', icon: 'fa-times-circle', label: 'مغلق', headerColor: 'var(--danger-color)' },
    sever_traffic_jam: { color: 'var(--warning-color)', icon: 'fa-traffic-light', label: 'ازدحام مروري', headerColor: 'var(--warning-color)' },
    unknown: { color: 'var(--unknown-color)', icon: 'fa-question-circle', label: 'غير معروف', headerColor: 'var(--unknown-color)' }
};

const PALESTINE_CENTER = [31.9522, 35.2332];
const DEFAULT_ZOOM = 8;
const DETAILED_ZOOM = 13; // Zoom level when focusing on a point or user
const MAX_ACCURACY_RADIUS_METERS = 1500; // For displaying accuracy circle

function initializeMap() {
    map = L.map('map', {
        zoomControl: false, // Using custom zoom controls
        attributionControl: true, // Keep OSM attribution
        preferCanvas: true // Can improve performance with many markers
    }).setView(PALESTINE_CENTER, DEFAULT_ZOOM);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
        maxZoom: 19,
        detectRetina: true
    }).addTo(map);

    
    // Add all marker layers to the map initially (they can be toggled)
    Object.values(markerLayers).forEach(layer => layer.addTo(map));

    console.log("Map initialized.");
}