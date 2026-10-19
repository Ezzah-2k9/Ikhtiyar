(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const mapElement = $('#map');
  if (!mapElement) return;

  const trafficAvailable = mapElement.dataset.trafficAvailable === 'true';
  const trafficButton = $('#traffic-toggle');
  const trafficStatus = $('#traffic-status');
  const trafficLegend = $('#traffic-legend');
  let trafficLayer = null;
  let trafficVisible = false;
  let trafficDiagnosticStarted = false;
  let successfulTrafficTiles = 0;

  async function explainTrafficFailure(event) {
    if (trafficDiagnosticStarted) return;
    trafficDiagnosticStarted = true;
    const tile = event?.coords;
    if (!tile || !Number.isInteger(tile.z) || !Number.isInteger(tile.x) || !Number.isInteger(tile.y)) {
      trafficStatus.textContent = 'Traffic tiles failed to load. Check Render logs for the TomTom response status.';
      return;
    }
    try {
      const response = await fetch(`/api/traffic/${tile.z}/${tile.x}/${tile.y}.png`, { cache: 'no-store' });
      const contentType = response.headers.get('content-type') || '';
      const payload = contentType.includes('application/json')
        ? await response.json().catch(() => null)
        : null;
      if (!payload) {
        trafficStatus.textContent = `The app host returned HTTP ${response.status}, not a traffic diagnostic. Check Render service logs; this is not a TomTom key-status response.`;
        return;
      }
      const reason = String(payload.error || 'Traffic tile request failed.');
      if (/HTTP 401/.test(reason)) {
        trafficStatus.textContent = 'TomTom did not accept TOMTOM_KEY. Verify the key in Render, save it, then redeploy.';
      } else if (/HTTP 403/.test(reason)) {
        trafficStatus.textContent = 'TomTom denied access (403). The key may be valid but lacks Traffic Flow Raster API access; enable that product or use an eligible key in Render.';
      } else if (/HTTP 429/.test(reason)) {
        trafficStatus.textContent = 'TomTom traffic quota or rate limit reached. Check your TomTom plan and usage.';
      } else if (/HTTP 5\d\d/.test(reason) || /temporarily unavailable/i.test(reason)) {
        trafficStatus.textContent = 'TomTom traffic is temporarily unavailable. Try again later.';
      } else {
        trafficStatus.textContent = `Traffic overlay failed: ${reason} Check the latest Render service logs for details.`;
      }
    } catch (_error) {
      trafficStatus.textContent = 'Could not read the traffic error details. Check the latest Render service logs.';
    }
  }

  function showToast(message) {
    const toast = $('#feature-toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('is-visible');
    window.setTimeout(() => toast.classList.remove('is-visible'), 5200);
  }

  window.IkhtiyarFeatures = { showToast };

  if (trafficButton && trafficStatus) {
    if (!trafficAvailable) {
      trafficButton.disabled = true;
      trafficButton.setAttribute('aria-pressed', 'false');
      trafficStatus.textContent = 'Add TOMTOM_KEY in Render to enable live traffic.';
    } else {
      trafficStatus.textContent = 'Live traffic is off.';
      trafficButton.addEventListener('click', () => {
        if (!window.map) return;
        if (!trafficLayer) {
          trafficLayer = L.tileLayer('/api/traffic/{z}/{x}/{y}.png', {
            tileSize: 256,
            opacity: 0.88,
            maxZoom: 22,
            attribution: 'Traffic flow © TomTom',
            crossOrigin: 'anonymous',
          });
          trafficLayer.on('tileload', () => {
            successfulTrafficTiles += 1;
            if (trafficVisible) {
              if (trafficLegend) trafficLegend.hidden = false;
              trafficStatus.textContent = 'Live TomTom traffic flow loaded. Colors show relative traffic speed, not a route ETA.';
            }
          });
          trafficLayer.on('tileerror', (event) => {
            if (successfulTrafficTiles === 0) {
              if (trafficLegend) trafficLegend.hidden = true;
              explainTrafficFailure(event);
            }
          });
        }
        trafficVisible = !trafficVisible;
        if (trafficVisible) trafficLayer.addTo(window.map);
        else window.map.removeLayer(trafficLayer);
        trafficButton.setAttribute('aria-pressed', String(trafficVisible));
        trafficButton.textContent = trafficVisible ? 'Hide traffic' : 'Show traffic';
        trafficDiagnosticStarted = false;
        successfulTrafficTiles = 0;
        if (trafficLegend) trafficLegend.hidden = true;
        trafficStatus.textContent = trafficVisible ? 'Connecting to live TomTom traffic…' : 'Live traffic is off.';
      });
    }
  }

  const weatherPanel = $('#weather-advisory');
  const routeEstimateNote = $('#route-estimate-note');
  window.addEventListener('ikhtiyar:route-results', (event) => {
    const weather = event.detail?.weather;
    if (routeEstimateNote) {
      routeEstimateNote.textContent = event.detail?.route_estimate_note || '';
      routeEstimateNote.hidden = !event.detail?.route_estimate_note;
    }
    if (!weatherPanel || !weather) return;
    weatherPanel.replaceChildren();
    weatherPanel.classList.remove('is-warning', 'is-caution');
    const heading = document.createElement('h3');
    heading.textContent = weather.is_live
      ? `Destination weather · ${weather.temp?.toFixed(0)}°C · ${weather.condition}`
      : 'Live destination weather unavailable';
    weatherPanel.appendChild(heading);

    if (weather.is_live && Array.isArray(weather.advisories) && weather.advisories.length) {
      const list = document.createElement('ul');
      weather.advisories.forEach((advisory) => {
        const item = document.createElement('li');
        item.textContent = `${advisory.title}: ${advisory.message}`;
        list.appendChild(item);
        if (advisory.severity === 'warning') weatherPanel.classList.add('is-warning');
        else weatherPanel.classList.add('is-caution');
      });
      weatherPanel.appendChild(list);
    } else {
      const message = document.createElement('p');
      message.textContent = weather.is_live
        ? `${weather.description || 'Current conditions are available.'} No travel advisory was triggered.`
        : 'No warning can be confirmed without live conditions.';
      weatherPanel.appendChild(message);
    }
    const disclaimer = document.createElement('p');
    disclaimer.className = 'disclaimer';
    disclaimer.textContent = `${weather.source ? `Weather source: ${weather.source}. ` : ''}${weather.advisory_disclaimer || 'Forecast-based guidance is not an official emergency warning.'}`;
    weatherPanel.appendChild(disclaimer);
    weatherPanel.classList.add('is-visible');
  });

  const favoriteOrigin = $('#saved-origin-select');
  const favoriteDestination = $('#saved-destination-select');
  const originInput = $('#origin');
  const destinationInput = $('#destination');
  const dialog = $('#save-place-dialog');
  const saveForm = $('#save-place-form');
  let savedPlaces = [];
  let saveTarget = null;

  function fillPlaceSelect(select) {
    if (!select) return;
    const first = select.querySelector('option');
    select.replaceChildren();
    if (first) select.appendChild(first);
    savedPlaces.forEach((place) => {
      const option = document.createElement('option');
      option.value = place.destination_id;
      option.textContent = `${place.label} — ${place.place_name}`;
      option.dataset.placeName = place.place_name;
      option.dataset.savedId = place.destination_id;
      if (place.latitude != null && place.longitude != null) {
        option.dataset.lat = place.latitude;
        option.dataset.lon = place.longitude;
      }
      select.appendChild(option);
    });
  }

  async function loadSavedPlaces() {
    try {
      const response = await fetch('/api/saved-destinations', { headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      savedPlaces = Array.isArray(data.destinations) ? data.destinations : [];
      fillPlaceSelect(favoriteOrigin);
      fillPlaceSelect(favoriteDestination);
    } catch (error) {
      console.warn('Saved places could not be loaded.', error);
    }
  }

  function applySavedPlace(select, input) {
    select?.addEventListener('change', () => {
      const option = select.selectedOptions[0];
      if (option?.dataset.placeName && input) {
        input.value = option.dataset.placeName;
        input.dataset.lat = option.dataset.lat || '';
        input.dataset.lon = option.dataset.lon || '';
        input.dataset.savedId = option.dataset.savedId || '';
      }
    });
  }

  applySavedPlace(favoriteOrigin, originInput);
  applySavedPlace(favoriteDestination, destinationInput);
  [originInput, destinationInput].forEach((input) => input?.addEventListener('input', () => {
    delete input.dataset.lat;
    delete input.dataset.lon;
    delete input.dataset.savedId;
  }));
  loadSavedPlaces();

  $$('[data-save-place]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!dialog || !saveForm) return;
      saveTarget = button.dataset.savePlace;
      const placeInput = saveTarget === 'origin' ? originInput : destinationInput;
      const targetName = $('#save-place-target');
      const valueField = $('#save-place-location');
      const labelField = $('#save-place-label');
      const latitudeField = $('#save-place-latitude');
      const longitudeField = $('#save-place-longitude');
      if (!placeInput?.value.trim()) {
        showToast('Enter a place before saving it.');
        return;
      }
      targetName.textContent = saveTarget === 'origin' ? 'starting point' : 'destination';
      valueField.value = placeInput.value.trim();
      labelField.value = '';
      let latitude = placeInput.dataset.lat || '';
      let longitude = placeInput.dataset.lon || '';
      const lastRoute = window.IkhtiyarLastRoute;
      const requestedName = lastRoute?.[`requested_${saveTarget}_name`];
      const resolved = lastRoute?.[saveTarget];
      if (!latitude && requestedName?.trim().toLowerCase() === placeInput.value.trim().toLowerCase() && resolved) {
        latitude = resolved.lat;
        longitude = resolved.lon;
      }
      latitudeField.value = latitude;
      longitudeField.value = longitude;
      dialog.showModal();
      labelField.focus();
    });
  });

  $('#save-place-cancel')?.addEventListener('click', () => dialog?.close());

  saveForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const label = $('#save-place-label').value.trim();
    const placeName = $('#save-place-location').value.trim();
    if (label.length < 2 || label.length > 40 || placeName.length < 2 || placeName.length > 140) {
      showToast('Use a 2–40 character name and a place under 140 characters.');
      return;
    }
    try {
      const response = await fetch('/api/saved-destinations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          label,
          place_name: placeName,
          latitude: $('#save-place-latitude').value ? Number($('#save-place-latitude').value) : null,
          longitude: $('#save-place-longitude').value ? Number($('#save-place-longitude').value) : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        showToast(data.error || 'The place could not be saved.');
        return;
      }
      dialog.close();
      showToast(`${label} saved to your top destinations.`);
      await loadSavedPlaces();
      const select = saveTarget === 'origin' ? favoriteOrigin : favoriteDestination;
      if (select) {
        const created = savedPlaces.find((place) => place.destination_id === data.destination.destination_id);
        if (created) {
          select.value = String(created.destination_id);
          applySavedPlaceValue(select, saveTarget === 'origin' ? originInput : destinationInput);
        }
      }
    } catch (error) {
      showToast('Could not reach Ikhtiyar. Please try again.');
    }
  });

  function applySavedPlaceValue(select, input) {
    const option = select?.selectedOptions[0];
    if (option?.dataset.placeName && input) {
      input.value = option.dataset.placeName;
      input.dataset.lat = option.dataset.lat || '';
      input.dataset.lon = option.dataset.lon || '';
      input.dataset.savedId = option.dataset.savedId || '';
    }
  }

  window.addEventListener('ikhtiyar:reward', (event) => {
    const reward = event.detail || {};
    const messages = [];
    if (reward.xp_awarded) messages.push(`+${reward.xp_awarded} XP earned.`);
    if (reward.current_streak) messages.push(`${reward.current_streak}-day travel streak.`);
    (reward.challenge_rewards || []).forEach((item) => messages.push(`Challenge complete: +${item.points_awarded} XP.`));
    if (messages.length) showToast(messages.join(' '));
  });
})();
