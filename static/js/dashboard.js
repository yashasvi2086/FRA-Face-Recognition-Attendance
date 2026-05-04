// static/js/dashboard.js

document.addEventListener("DOMContentLoaded", () => {
    const trainBtn = document.getElementById("trainBtn");
    const trainProgress = document.getElementById("trainProgress");
    const trainMsg = document.getElementById("trainMsg");

    let chart = null;

    // ===============================
    // TRAINING STATUS POLL
    // ===============================
    async function pollStatus() {
        try {
            const res = await fetch("/train_status");

            if (!res.ok) {
                trainMsg.innerText = "Error fetching training status";
                return null;
            }

            const data = await res.json();

            trainProgress.style.width = data.progress + "%";
            trainProgress.innerText = data.progress + "%";
            trainMsg.innerText = data.message || "Processing...";

            return data;

        } catch (err) {
            console.error("Polling error:", err);
            trainMsg.innerText = "Server error during training";
            return null;
        }
    }

    // ===============================
    // START TRAINING
    // ===============================
    if (trainBtn) {
        trainBtn.addEventListener("click", async () => {
            trainBtn.disabled = true;
            trainMsg.innerText = "Training started...";

            try {
                const start = await fetch("/train_model");

                if (!start.ok) {
                    alert("Failed to start training");
                    trainBtn.disabled = false;
                    return;
                }

                const interval = setInterval(async () => {
                    const status = await pollStatus();

                    if (status && status.progress >= 100) {
                        clearInterval(interval);
                        trainBtn.disabled = false;
                        trainMsg.innerText = "Training completed successfully ✔";
                    }
                }, 1200);

            } catch (err) {
                console.error(err);
                alert("Server error");
                trainBtn.disabled = false;
            }
        });
    }

    // ===============================
    // DASHBOARD STATS
    // ===============================
    async function updateDashboardStats() {
        try {
            const res = await fetch("/dashboard_stats");
            if (!res.ok) return;

            const data = await res.json();

            // Counters
            const totalStudents = document.getElementById("totalStudents");
            const attendanceToday = document.getElementById("attendanceToday");
            const totalClasses = document.getElementById("totalClasses");

            if (totalStudents) totalStudents.innerText = data.total_students || 0;
            if (attendanceToday) attendanceToday.innerText = data.attendance_today || 0;
            if (totalClasses) totalClasses.innerText = data.total_classes || 0;

            // Activity
            const recentList = document.getElementById("recentActivityList");

            if (recentList && data.recent_activity) {
                if (data.recent_activity.length === 0) {
                    recentList.innerHTML = `
                        <p class="mono" style="font-size:11px;color:#64748b;text-align:center;padding:20px;">
                            NO_RECENT_LOGS
                        </p>`;
                    return;
                }

                recentList.innerHTML = data.recent_activity.map(act => {
                    const timeStr = new Date(act.time).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit'
                    });

                    return `
                        <div class="activity-item">
                            <div class="act-name">${act.name}</div>
                            <div class="badge-match">IDENTIFIED</div>
                            <div class="act-time mono">${timeStr}</div>
                        </div>
                    `;
                }).join('');
            }

        } catch (err) {
            console.error("Dashboard stats error:", err);
        }
    }

    // ===============================
    // CHART
    // ===============================
    async function updateChart() {
        try {
            const res = await fetch("/attendance_stats");

            if (!res.ok) {
                console.warn("attendance_stats route not found");
                return;
            }

            const data = await res.json();
            const canvas = document.getElementById("attendanceChart");

            if (!canvas) return;

            const ctx = canvas.getContext("2d");

            if (!chart) {
                chart = new Chart(ctx, {
                    type: "line",
                    data: {
                        labels: data.dates || [],
                        datasets: [{
                            label: "Daily Attendance",
                            data: data.counts || [],
                            borderColor: "#22d3ee",
                            backgroundColor: "rgba(6,182,212,0.1)",
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true,
                            pointBackgroundColor: "#22d3ee"
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                backgroundColor: "rgba(15,23,42,0.9)"
                            }
                        },
                        scales: {
                            x: {
                                grid: {
                                    color: "rgba(255,255,255,0.05)"
                                },
                                ticks: {
                                    color: "#64748b"
                                }
                            },
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: "rgba(255,255,255,0.05)"
                                },
                                ticks: {
                                    precision: 0,
                                    color: "#64748b"
                                }
                            }
                        }
                    }
                });

            } else {
                chart.data.labels = data.dates || [];
                chart.data.datasets[0].data = data.counts || [];
                chart.update();
            }

        } catch (err) {
            console.error("Chart error:", err);
        }
    }

    // ===============================
    // INIT
    // ===============================
    updateChart();
    updateDashboardStats();

    setInterval(() => {
        updateChart();
        updateDashboardStats();
    }, 10000);
});