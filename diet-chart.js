document.addEventListener('DOMContentLoaded', async function() {
    const loginPrompt = document.getElementById('loginPrompt');
    const chartsSection = document.getElementById('chartsSection');
    const ctx = document.getElementById('trendChart').getContext('2d');

    // Try to fetch user plans (requires login)
    let plans = [];
    try {
        const res = await fetch('http://127.0.0.1:5000/user_plans', { credentials: 'include' });
        if (res.status === 401) {
            loginPrompt.style.display = 'block';
            chartsSection.style.display = 'none';
            return;
        }
        const data = await res.json();
        plans = data.plans;
    } catch (err) {
        loginPrompt.style.display = 'block';
        chartsSection.style.display = 'none';
        return;
    }
    if (!plans.length) {
        chartsSection.innerHTML = '<em>No data to display. Upload reports to see trends.</em>';
        chartsSection.style.display = 'block';
        return;
    }
    // Extract trends for key parameters
    const dates = plans.map(p => new Date(p.timestamp).toLocaleDateString());
    function getTrend(param) {
        return plans.map(p => (p.values && p.values[param]) ? p.values[param] : null);
    }
    const hemoglobin = getTrend('hemoglobin');
    const glucose = getTrend('glucose');
    const cholesterol = getTrend('cholesterol');
    // Plot with Chart.js
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    label: 'Hemoglobin',
                    data: hemoglobin,
                    borderColor: '#2d6a4f',
                    fill: false
                },
                {
                    label: 'Glucose',
                    data: glucose,
                    borderColor: '#e76f51',
                    fill: false
                },
                {
                    label: 'Cholesterol',
                    data: cholesterol,
                    borderColor: '#457b9d',
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Key Health Parameters Over Time' }
            },
            scales: {
                y: { beginAtZero: false }
            }
        }
    });
    chartsSection.style.display = 'block';
    loginPrompt.style.display = 'none';
}); 