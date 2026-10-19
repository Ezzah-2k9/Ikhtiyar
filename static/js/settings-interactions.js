(() => {
  'use strict';

  const tabs = [...document.querySelectorAll('[data-settings-tab]')];
  const panels = [...document.querySelectorAll('[data-settings-panel]')];
  if (!tabs.length || !panels.length) return;

  function activate(name, moveFocus = false) {
    tabs.forEach((tab) => {
      const selected = tab.dataset.settingsTab === name;
      tab.classList.toggle('active', selected);
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && moveFocus) tab.focus();
    });
    panels.forEach((panel) => {
      const selected = panel.dataset.settingsPanel === name;
      panel.hidden = !selected;
      panel.classList.toggle('active', selected);
    });
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activate(tab.dataset.settingsTab));
    tab.addEventListener('keydown', (event) => {
      let next = null;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== null) {
        event.preventDefault();
        activate(tabs[next].dataset.settingsTab, true);
      }
    });
  });

  document.querySelectorAll('[data-range-input]').forEach((input) => {
    const output = document.querySelector(`[data-range-output="${input.id}"]`);
    const update = () => {
      const minimum = Number(input.min || 0);
      const maximum = Number(input.max || 100);
      const value = Number(input.value || minimum);
      const progress = maximum === minimum ? 0 : ((value - minimum) / (maximum - minimum)) * 100;
      input.style.setProperty('--range-progress', `${progress}%`);
      if (output) output.value = `${value}/10`;
    };
    input.addEventListener('input', update);
    update();
  });

  const goalType = document.querySelector('#monthly-goal-type');
  const goalTarget = document.querySelector('#monthly-goal-target');
  const goalLabel = document.querySelector('[data-goal-target-label]');
  const goalCurrent = document.querySelector('[data-goal-current]');
  const goalOptions = {
    co2_savings: { title: 'CO₂ savings', unit: 'kg CO₂', max: 1000, step: '0.1', example: '10' },
    spending_limit: { title: 'Transport budget', unit: 'AED', max: 100000, step: '1', example: '500' },
    trip_count: { title: 'Trips this month', unit: 'trips', max: 500, step: '1', example: '20' },
    sustainable_trips: { title: 'Lower-impact trips', unit: 'trips', max: 500, step: '1', example: '10' },
    active_distance: { title: 'Active travel distance', unit: 'km', max: 5000, step: '1', example: '25' },
  };
  if (goalType && goalTarget) {
    const updateGoalFields = (clearValue = false) => {
      const option = goalOptions[goalType.value] || goalOptions.co2_savings;
      if (goalLabel) goalLabel.innerHTML = `This month’s target <span>${option.unit}</span>`;
      goalTarget.max = String(option.max);
      goalTarget.step = option.step;
      goalTarget.placeholder = `e.g., ${option.example}`;
      if (clearValue) goalTarget.value = '';
      if (goalCurrent && !goalTarget.value) {
        goalCurrent.textContent = `Enter your ${option.title.toLowerCase()} target for this month.`;
      }
    };
    goalType.addEventListener('change', () => updateGoalFields(true));
    updateGoalFields();
  }

  const selected = tabs.find((tab) => tab.getAttribute('aria-selected') === 'true') || tabs[0];
  activate(selected.dataset.settingsTab);
})();
