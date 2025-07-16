// Upload & Analyze
document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) return;
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const resultSection = document.getElementById('resultSection');
    resultSection.style.display = 'none';

    try {
        const res = await fetch('http://127.0.0.1:5000/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        updateDashboardCards(data.dashboard_stats); // new function
        updateMilestones(data.milestones);          // new function
        updateWellness(data.wellness);              // new function

        const conditionList = document.getElementById('conditionList');
        conditionList.innerHTML = '';
        if (data.conditions && data.conditions.length) {
            data.conditions.forEach(cond => {
                const li = document.createElement('li');
                li.textContent = cond;
                conditionList.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'No specific health condition detected.';
            conditionList.appendChild(li);
        }

        const tbody = document.querySelector('#dietTable tbody');
        tbody.innerHTML = '';
        if (data.diet_chart && data.diet_chart.length) {
            data.diet_chart.forEach(meal => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${meal.meal}</td><td>${meal.time}</td><td>${meal.items.join(', ')}</td>`;
                tbody.appendChild(tr);
            });
            setMealAlarms(data.diet_chart);
        }

        displayExtractedTable(data.all_extracted);
        resultSection.style.display = 'block';
    } catch (err) {
        alert('Failed to upload or process the file.');
    }
});

// Set Meal Alarms
function setMealAlarms(dietChart) {
    if (window.mealAlarmTimeouts) {
        window.mealAlarmTimeouts.forEach(timeout => clearTimeout(timeout));
    }
    window.mealAlarmTimeouts = [];
    const now = new Date();
    dietChart.forEach(meal => {
        const mealTime = parseTime(meal.time);
        if (!mealTime) return;
        let alarmTime = new Date(now);
        alarmTime.setHours(mealTime.hours, mealTime.minutes, 0, 0);
        if (alarmTime < now) alarmTime.setDate(alarmTime.getDate() + 1);
        const msUntilAlarm = alarmTime - now;
        const timeout = setTimeout(() => {
            alert(`Meal Reminder: It's time for your ${meal.meal} (${meal.items.join(', ')})`);
        }, msUntilAlarm);
        window.mealAlarmTimeouts.push(timeout);
    });
}

function parseTime(timeStr) {
    const match = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
    if (!match) return null;
    let hours = parseInt(match[1]);
    const minutes = parseInt(match[2]);
    const ampm = match[3];
    if (ampm) {
        if (ampm.toUpperCase() === 'PM' && hours < 12) hours += 12;
        if (ampm.toUpperCase() === 'AM' && hours === 12) hours = 0;
    }
    return { hours, minutes };
}

// Display extracted parameters
function displayExtractedTable(allExtracted) {
    let section = document.getElementById('extractedTableSection');
    if (!section) {
        section = document.createElement('section');
        section.id = 'extractedTableSection';
        document.querySelector('main').appendChild(section);
    }
    section.innerHTML = '<h2>Extracted Medical Parameters</h2>';
    if (!allExtracted || !allExtracted.length) {
        section.innerHTML += '<em>No medical parameters extracted from the report.</em>';
        return;
    }
    let table = `<table><thead><tr><th>Test Name</th><th>Value</th><th>Normal Range</th><th>Unit</th><th>Status</th></tr></thead><tbody>`;
    allExtracted.forEach(row => {
        let statusClass = row.Status === 'Normal' ? 'status-normal' : (row.Status === 'Low' ? 'status-low' : (row.Status === 'High' ? 'status-high' : 'status-check'));
        table += `<tr><td>${row['Test Name']}</td><td>${row.Value}</td><td>${row['Normal Range']}</td><td>${row.Unit}</td><td class="${statusClass}">${row.Status}</td></tr>`;
    });
    table += '</tbody></table>';
    section.innerHTML += table;
}

// Previous Plans
window.addEventListener('DOMContentLoaded', fetchPreviousPlans);
function fetchPreviousPlans() {
    fetch('http://127.0.0.1:5000/plans')
        .then(res => res.json())
        .then(data => {
            const plansSection = document.getElementById('plansSection');
            if (!plansSection) return;
            plansSection.innerHTML = '';
            if (data.plans && data.plans.length) {
                data.plans.slice(-5).reverse().forEach(plan => {
                    const div = document.createElement('div');
                    div.className = 'plan-card';
                    div.innerHTML = `<strong>${plan.filename}</strong> <em>(${new Date(plan.timestamp).toLocaleString()})</em><br>
                        <b>Conditions:</b> ${plan.conditions.join(', ') || 'None'}<br>
                        <b>Diet Chart:</b> ${plan.diet_chart.map(m => `${m.meal} (${m.time}): ${m.items.join(', ')}`).join('<br>')}`;
                    plansSection.appendChild(div);
                });
            } else {
                plansSection.innerHTML = '<em>No previous plans found.</em>';
            }
        });
}

// 🆕 Dynamic Dashboard Update
function updateDashboardCards(stats = {}) {
    const cardMappings = {
        'health-card': `Health: ${stats.health_status || 'N/A'}`,
        'exercise-card': `Calories Burned: ${stats.calories || '0'} kcal`,
        'nutrition-card': `Nutrition: ${stats.nutrition_summary || 'N/A'}`,
        'activity-card': `Steps: ${stats.steps || '0'}`,
        'milestones-card': `Milestones: ${stats.milestones || 0}`,
        'wellness-card': `Score: ${stats.wellness_score || 'N/A'}`
    };
    for (const [cardClass, content] of Object.entries(cardMappings)) {
        const card = document.querySelector(`.${cardClass} .card-desc`);
        if (card) card.textContent = content;
    }
}

// 🆕 Milestones Update
function updateMilestones(milestones = []) {
    const container = document.getElementById('milestonesList');
    if (!container) return;
    container.innerHTML = '';
    if (milestones.length) {
        milestones.forEach(m => {
            const div = document.createElement('div');
            div.className = 'milestone-badge';
            div.textContent = m;
            container.appendChild(div);
        });
    } else {
        container.innerHTML = '<em>No milestones yet.</em>';
    }
}

// 🆕 Wellness Update
function updateWellness(wellness = {}) {
    const scoreDiv = document.getElementById('wellnessScore');
    const tipsDiv = document.getElementById('wellnessTips');
    scoreDiv.textContent = `Wellness Score: ${wellness.score || 'N/A'}`;
    tipsDiv.innerHTML = (wellness.tips || []).map(t => `<li>${t}</li>`).join('');
}

document.getElementById('activityForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const steps = parseInt(document.getElementById('stepsInput').value) || 0;
    const calories = parseInt(document.getElementById('caloriesInput').value) || 0;
    const exercise = document.getElementById('exerciseInput').value || '';
    const payload = { steps, calories, exercise };

    try {
        const res = await fetch('http://127.0.0.1:5000/track_activity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.message) {
            document.getElementById('activitySummary').innerHTML =
                `<b>Today's Steps:</b> ${data.today_steps} <br>
                 <b>Today's Calories:</b> ${data.today_calories}`;
            // Optionally update dashboard cards
            updateDashboardCards({
                steps: data.today_steps,
                calories: data.today_calories
            });
        } else {
            document.getElementById('activitySummary').textContent = 'Failed to log activity.';
        }
    } catch (err) {
        document.getElementById('activitySummary').textContent = 'Error logging activity.';
    }
});

document.querySelectorAll('.sidebar a[data-section]').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const sectionId = this.getAttribute('data-section');
        document.querySelectorAll('main .dashboard-section').forEach(sec => {
            sec.style.display = (sec.id === sectionId) ? 'block' : 'none';
        });
    });
});
// Show the first section by default
document.addEventListener('DOMContentLoaded', () => {
    const firstSection = document.querySelector('main .dashboard-section');
    if (firstSection) firstSection.style.display = 'block';
    document.querySelectorAll('main .dashboard-section:not(:first-child)').forEach(sec => sec.style.display = 'none');
}); 