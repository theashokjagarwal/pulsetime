const titles = {
  dashboard: ["Overview", "Attendance dashboard"],
  attendance: ["Daily register", "Check-in and check-out"],
  employees: ["People", "Employee directory"],
  reports: ["Insights", "Attendance reports"],
};

const toastEl = document.getElementById("toast");
const employeeModal = document.getElementById("employeeModal");
const employeeForm = document.getElementById("employeeForm");
const employeeError = document.getElementById("employeeError");

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function formatTime(value) {
  return value ? value.slice(0, 5) : "-";
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.hidden = false;
  setTimeout(() => {
    toastEl.hidden = true;
  }, 2400);
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function setView(name) {
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${name}`));
  document.querySelectorAll(".nav-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === name));
  const [eyebrow, title] = titles[name];
  document.getElementById("pageEyebrow").textContent = eyebrow;
  document.getElementById("pageTitle").textContent = title;
  if (name === "dashboard") loadDashboard();
  if (name === "attendance") loadAttendance();
  if (name === "employees") loadEmployees();
  if (name === "reports") loadReports();
}

async function loadDashboard() {
  const data = await api("/api/dashboard");
  document.getElementById("statTotal").textContent = data.total_employees;
  document.getElementById("statPresent").textContent = data.present;
  document.getElementById("statLate").textContent = data.late;
  document.getElementById("statAbsent").textContent = data.absent;
  document.getElementById("deptList").innerHTML = data.departments.map((dept) => {
    const pct = dept.total ? Math.round((dept.on_site / dept.total) * 100) : 0;
    return `<div class="dept-row"><div><strong>${dept.department}</strong><div class="bar"><span style="width:${pct}%"></span></div></div><span>${dept.on_site}/${dept.total}</span></div>`;
  }).join("");
  document.getElementById("recentList").innerHTML = data.recent.map((item) => `
    <div class="activity-row">
      <div>
        <strong>${item.name}</strong>
        <div>${item.department} · ${item.work_date}</div>
      </div>
      <span class="badge ${item.status}">${item.status}</span>
    </div>
  `).join("") || "<p>No recent activity.</p>";
}

async function loadAttendance() {
  const date = document.getElementById("attendanceDate").value || todayISO();
  document.getElementById("attendanceDate").value = date;
  const data = await api(`/api/attendance?date=${date}`);
  document.getElementById("attendanceBody").innerHTML = data.records.map((row) => {
    const canIn = !row.check_in;
    const canOut = row.check_in && !row.check_out;
    return `
      <tr>
        <td><strong>${row.name}</strong><div>${row.code}</div></td>
        <td>${row.department}</td>
        <td>${formatTime(row.check_in)}</td>
        <td>${formatTime(row.check_out)}</td>
        <td>${row.hours ?? "-"}</td>
        <td><span class="badge ${row.status}">${row.status}</span></td>
        <td class="actions">
          <button class="tiny ok" ${canIn ? "" : "disabled"} data-action="in" data-id="${row.employee_id}">Check in</button>
          <button class="tiny" ${canOut ? "" : "disabled"} data-action="out" data-id="${row.employee_id}">Check out</button>
          <button class="tiny warn" data-action="absent" data-id="${row.employee_id}">Absent</button>
        </td>
      </tr>
    `;
  }).join("");
}

async function loadEmployees(q = "") {
  const data = await api(`/api/employees?q=${encodeURIComponent(q)}`);
  document.getElementById("employeeBody").innerHTML = data.map((emp) => `
    <tr>
      <td>${emp.code}</td>
      <td>${emp.name}</td>
      <td>${emp.department}</td>
      <td>${emp.role}</td>
      <td>${emp.email}</td>
      <td><span class="badge ${emp.status}">${emp.status}</span></td>
    </tr>
  `).join("");
}

async function loadReports() {
  const from = document.getElementById("reportFrom").value || daysAgo(6);
  const to = document.getElementById("reportTo").value || todayISO();
  document.getElementById("reportFrom").value = from;
  document.getElementById("reportTo").value = to;
  const data = await api(`/api/reports?from=${from}&to=${to}`);
  document.getElementById("dailyBars").innerHTML = data.daily.map((day) => `
    <div class="day-card">
      <span>${day.work_date.slice(5)}</span>
      <strong>${(day.present || 0) + (day.late || 0)}</strong>
      <small>${day.late || 0} late · ${day.absent || 0} absent</small>
    </div>
  `).join("") || "<p>No records in this range.</p>";
  document.getElementById("reportBody").innerHTML = data.employees.map((emp) => `
    <tr>
      <td><strong>${emp.name}</strong><div>${emp.code} · ${emp.department}</div></td>
      <td>${emp.present_days || 0}</td>
      <td>${emp.late_days || 0}</td>
      <td>${emp.absent_days || 0}</td>
      <td>${emp.days_recorded || 0}</td>
    </tr>
  `).join("");
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});

document.getElementById("refreshAttendance").addEventListener("click", loadAttendance);
document.getElementById("attendanceDate").addEventListener("change", loadAttendance);
document.getElementById("loadReports").addEventListener("click", loadReports);
document.getElementById("employeeSearch").addEventListener("input", (e) => loadEmployees(e.target.value));
document.getElementById("openEmployeeModal").addEventListener("click", () => {
  employeeError.textContent = "";
  employeeForm.reset();
  employeeModal.hidden = false;
});
document.getElementById("closeEmployeeModal").addEventListener("click", () => {
  employeeModal.hidden = true;
});

employeeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(employeeForm);
  const payload = Object.fromEntries(form.entries());
  try {
    await api("/api/employees", { method: "POST", body: JSON.stringify(payload) });
    employeeModal.hidden = true;
    showToast("Employee added");
    loadEmployees();
    loadDashboard();
  } catch (err) {
    employeeError.textContent = err.message;
  }
});

document.getElementById("attendanceBody").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const employee_id = Number(btn.dataset.id);
  const date = document.getElementById("attendanceDate").value || todayISO();
  const routes = {
    in: "/api/attendance/check-in",
    out: "/api/attendance/check-out",
    absent: "/api/attendance/mark-absent",
  };
  try {
    await api(routes[btn.dataset.action], {
      method: "POST",
      body: JSON.stringify({ employee_id, date }),
    });
    showToast("Attendance updated");
    loadAttendance();
    loadDashboard();
  } catch (err) {
    showToast(err.message);
  }
});

function tickClock() {
  const now = new Date();
  document.getElementById("clockLabel").textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  document.getElementById("todayChip").textContent = now.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

document.getElementById("attendanceDate").value = todayISO();
document.getElementById("reportFrom").value = daysAgo(6);
document.getElementById("reportTo").value = todayISO();
tickClock();
setInterval(tickClock, 30000);
setView("dashboard");
