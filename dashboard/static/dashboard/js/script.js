// Kilo Gateway Dashboard JavaScript

document.addEventListener("DOMContentLoaded", function () {
    const themeToggle = document.getElementById("theme-toggle");
    const themeIcon = document.getElementById("theme-icon");
    const htmlElement = document.documentElement;

    // Load saved theme or check system preference
    const savedTheme = localStorage.getItem("kilo-theme");
    const initialTheme = savedTheme || "dark";

    htmlElement.setAttribute("data-theme", initialTheme);
    themeIcon.textContent = initialTheme === "dark" ? "☀️" : "🌙";

    // Theme toggle handler
    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            const currentTheme = htmlElement.getAttribute("data-theme");
            const newTheme = currentTheme === "dark" ? "light" : "dark";
            htmlElement.setAttribute("data-theme", newTheme);
            localStorage.setItem("kilo-theme", newTheme);
            themeIcon.textContent = newTheme === "dark" ? "☀️" : "🌙";
        });
    }

    const providerSelect = document.getElementById("provider");
    const reasoningSelect = document.getElementById("reasoning");
    const searchInput = document.getElementById("search");
    const filterForm = document.getElementById("filter-form");

    // Submitting the form rebuilds the query string from only the named
    // inputs (search, provider, reasoning), discarding any stray params.
    function submitFilterForm() {
        if (filterForm) {
            filterForm.submit();
        }
    }

    // Apply provider filter on change
    if (providerSelect) {
        providerSelect.addEventListener("change", submitFilterForm);
    }

    // Apply reasoning filter on change
    if (reasoningSelect) {
        reasoningSelect.addEventListener("change", submitFilterForm);
    }

    // Search on Enter key (native form submit would also work; this keeps
    // the UX explicit and trims whitespace before submitting).
    if (searchInput) {
        searchInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                searchInput.value = searchInput.value.trim();
                submitFilterForm();
            }
        });
    }

    // View toggle (grid vs table)
    const viewToggle = document.getElementById("view-toggle");
    const viewIcon = document.getElementById("view-icon");
    const gridView = document.getElementById("models-grid");
    const tableView = document.getElementById("models-table");

    function applyView(view) {
        if (view === "table") {
            if (gridView) gridView.style.display = "none";
            if (tableView) tableView.style.display = "block";
            if (viewIcon) viewIcon.textContent = "⊞";
        } else {
            if (gridView) gridView.style.display = "grid";
            if (tableView) tableView.style.display = "none";
            if (viewIcon) viewIcon.textContent = "☰";
        }
    }

    var savedView = localStorage.getItem("kilo-view") || "grid";
    applyView(savedView);

    if (viewToggle) {
        viewToggle.addEventListener("click", function () {
            var current = (gridView && gridView.style.display === "none") ? "table" : "grid";
            var next = current === "grid" ? "table" : "grid";
            localStorage.setItem("kilo-view", next);
            applyView(next);
        });
    }

    initTableSort();
});

/**
 * Copy the full JSON for a model to the clipboard.
 * @param {string} modelId - The model ID (used as the json_script element id)
 * @param {HTMLElement} btn - The button that was clicked
 */
function copyModelJson(modelId, btn) {
    var el = document.getElementById(modelId);
    if (!el) {
        console.error("Raw JSON not found for model: " + modelId);
        return;
    }

    var text = el.textContent;
    try {
        var obj = JSON.parse(text);
        text = JSON.stringify(obj, null, 2);
    } catch (e) {
        // Fall back to the raw text if it isn't valid JSON.
    }

    navigator.clipboard.writeText(text).then(
        function () {
            const original = btn.innerHTML;
            btn.innerHTML = "✅";
            btn.classList.add("copied");
            setTimeout(function () {
                btn.innerHTML = original;
                btn.classList.remove("copied");
            }, 1500);
        },
        function (err) {
            console.error("Copy failed: ", err);
        }
    );
}

/**
 * Copy the raw API response (as-is) to the clipboard.
 * @param {HTMLElement} btn - The button that was clicked
 */
function copyAllJson(btn) {
    var el = document.getElementById("raw-all");
    if (!el) {
        console.error("Raw API JSON not found");
        return;
    }

    var text = el.textContent;
    try {
        // json_script embeds the raw text as a JSON string; unescape it.
        text = JSON.parse(text);
    } catch (e) {
        // Fall back to the raw text if it isn't valid JSON.
    }

    navigator.clipboard.writeText(text).then(
        function () {
            const original = btn.innerHTML;
            btn.innerHTML = "✅ Copied";
            btn.classList.add("copied");
            setTimeout(function () {
                btn.innerHTML = original;
                btn.classList.remove("copied");
            }, 1500);
        },
        function (err) {
            console.error("Copy failed: ", err);
        }
    );
}

/**
 * Copy a model ID (found next to the button) to the clipboard.
 * @param {HTMLElement} btn - The copy button that was clicked
 */
function copyModelId(btn) {
    var idEl = btn.parentElement.querySelector(".model-id, .td-id");
    var text = idEl ? idEl.textContent.trim() : "";
    navigator.clipboard.writeText(text).then(
        function () {
            var original = btn.innerHTML;
            btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            btn.classList.add("copied");
            setTimeout(function () {
                btn.innerHTML = original;
                btn.classList.remove("copied");
            }, 1500);
        },
        function (err) {
            console.error("Copy failed: ", err);
        }
    );
}

/**
 * Sortable table helpers.
 */
var tableSort = { column: null, ascending: true };

function initTableSort() {
    var headers = document.querySelectorAll(".data-table th.sortable");
    if (!headers.length) return;
    headers.forEach(function (th) {
        th.addEventListener("click", function () {
            var column = this.getAttribute("data-sort");
            if (tableSort.column === column) {
                tableSort.ascending = !tableSort.ascending;
            } else {
                tableSort.column = column;
                tableSort.ascending = true;
            }
            updateSortIndicators(column, tableSort.ascending);
            sortTable(column, tableSort.ascending);
        });
    });
}

function updateSortIndicators(column, ascending) {
    document.querySelectorAll(".data-table th.sortable").forEach(function (th) {
        th.classList.remove("sorted-asc", "sorted-desc");
        var ind = th.querySelector(".sort-indicator");
        if (ind) ind.remove();
        if (th.getAttribute("data-sort") === column) {
            th.classList.add(ascending ? "sorted-asc" : "sorted-desc");
            var span = document.createElement("span");
            span.className = "sort-indicator";
            span.textContent = ascending ? "▲" : "▼";
            th.appendChild(span);
        }
    });
}

function sortTable(column, ascending) {
    var tbody = document.querySelector(".data-table tbody");
    if (!tbody) return;
    var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
    rows.sort(function (a, b) {
        var aCell = a.querySelector('td[data-sort="' + column + '"]');
        var bCell = b.querySelector('td[data-sort="' + column + '"]');
        var aVal = getSortValue(aCell);
        var bVal = getSortValue(bCell);
        return compareValues(aVal, bVal, ascending);
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
}

function getSortValue(cell) {
    if (!cell) return "";
    var raw = cell.getAttribute("data-sort-value");
    if (raw !== null) return raw;
    return cell.textContent.trim();
}

function compareValues(a, b, ascending) {
    var aNum = Number(a);
    var bNum = Number(b);
    var result;
    if (a !== "" && b !== "" && !isNaN(aNum) && !isNaN(bNum)) {
        result = aNum - bNum;
    } else {
        a = String(a).toLowerCase();
        b = String(b).toLowerCase();
        if (a < b) result = -1;
        else if (a > b) result = 1;
        else result = 0;
    }
    return ascending ? result : -result;
}
