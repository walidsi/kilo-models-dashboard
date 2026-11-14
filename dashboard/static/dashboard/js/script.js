// Kilo Gateway Dashboard JavaScript

(function () {
    // Sync the view query param / cookie with localStorage before the page
    // renders, mirroring the server-side active_view logic.
    try {
        var params = new URLSearchParams(window.location.search);
        var viewParam = params.get("view");
        var view = viewParam || localStorage.getItem("kilo-view") || "grid";
        if (view !== "grid" && view !== "table") view = "grid";
        document.documentElement.setAttribute("data-view", view);
        if (!viewParam) {
            try {
                localStorage.setItem("kilo-view", view);
            } catch (e) {}
        }
    } catch (e) {}
})();

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
    const modalitySelect = document.getElementById("modality");
    const reasoningSelect = document.getElementById("reasoning");
    const searchInput = document.getElementById("search");
    const filterForm = document.getElementById("filter-form");

    // Submitting the form rebuilds the query string from only the named
    // inputs (search, provider, reasoning), discarding any stray params.
    function submitFilterForm() {
        if (filterForm) {
            // Preserve the current view across filter submissions.
            var view = document.documentElement.getAttribute("data-view") || "grid";
            var viewInput = filterForm.querySelector('input[name="view"]');
            if (!viewInput) {
                viewInput = document.createElement("input");
                viewInput.type = "hidden";
                viewInput.name = "view";
                filterForm.appendChild(viewInput);
            }
            viewInput.value = view;
            filterForm.submit();
        }
    }

    // Apply provider filter on change
    if (providerSelect) {
        providerSelect.addEventListener("change", submitFilterForm);
    }

    // Apply modality filter on change
    if (modalitySelect) {
        modalitySelect.addEventListener("change", submitFilterForm);
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

    // Search button handler
    const searchBtn = document.getElementById("search-btn");
    if (searchBtn && searchInput) {
        searchBtn.addEventListener("click", function () {
            searchInput.value = searchInput.value.trim();
            submitFilterForm();
        });
    }

    // Clear all filters button
    const clearFiltersBtn = document.getElementById("clear-filters-btn");
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener("click", function () {
            // Reset all filter values
            if (searchInput) searchInput.value = "";
            if (providerSelect) providerSelect.value = "";
            if (modalitySelect) modalitySelect.value = "";
            if (reasoningSelect) reasoningSelect.value = "";
            submitFilterForm();
        });
    }

    // Individual filter chip removal
    const filterChips = document.querySelectorAll(".filter-chip");
    filterChips.forEach(function (chip) {
        const removeBtn = chip.querySelector(".chip-remove");
        if (removeBtn) {
            removeBtn.addEventListener("click", function () {
                const filterType = chip.getAttribute("data-filter");
                // Reset the corresponding filter control
                if (filterType === "search" && searchInput) {
                    searchInput.value = "";
                } else if (filterType === "provider" && providerSelect) {
                    providerSelect.value = "";
                } else if (filterType === "modality" && modalitySelect) {
                    modalitySelect.value = "";
                } else if (filterType === "reasoning" && reasoningSelect) {
                    reasoningSelect.value = "";
                }
                submitFilterForm();
            });
        }
    });

    // View toggle (grid vs table)
    const viewToggle = document.getElementById("view-toggle");
    const viewIcon = document.getElementById("view-icon");
    const htmlEl = document.documentElement;

    function applyView(view) {
        htmlEl.setAttribute("data-view", view);
        if (viewIcon) viewIcon.textContent = view === "table" ? "⊞" : "☰";
    }

    // The inline <head> script already set data-view before paint; sync the
    // toggle icon with it here.
    applyView(htmlEl.getAttribute("data-view") || "grid");

    if (viewToggle) {
        viewToggle.addEventListener("click", function () {
            var current = htmlEl.getAttribute("data-view") || "grid";
            var next = current === "grid" ? "table" : "grid";
            localStorage.setItem("kilo-view", next);
            // Reload so the server can render only the requested view. This
            // avoids keeping both heavy subtrees in the DOM.
            var url = new URL(window.location.href);
            url.searchParams.set("view", next);
            window.location.href = url.toString();
        });
    }

    initTableSort();
});

/**
 * Fetch JSON lazily from a URL, pretty-print it, and copy to the clipboard.
 * @param {string} url - The endpoint to fetch
 * @param {HTMLElement} btn - The button that was clicked
 * @param {string} successLabel - Temporary label to show on success
 */
function fetchAndCopyJson(url, btn, successLabel) {
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = "⏳";

    fetch(url)
        .then(function (response) {
            if (!response.ok) throw new Error("HTTP " + response.status);
            return response.json();
        })
        .then(function (data) {
            var text = JSON.stringify(data, null, 2);
            return navigator.clipboard.writeText(text);
        })
        .then(function () {
            btn.innerHTML = successLabel;
            btn.classList.add("copied");
            setTimeout(function () {
                btn.innerHTML = original;
                btn.classList.remove("copied");
                btn.disabled = false;
            }, 1500);
        })
        .catch(function (err) {
            console.error("Copy failed: ", err);
            btn.innerHTML = original;
            btn.disabled = false;
        });
}

/**
 * Copy the full JSON for a model to the clipboard.
 * @param {string} modelId - The model ID
 * @param {HTMLElement} btn - The button that was clicked
 */
function copyModelJson(modelId, btn) {
    fetchAndCopyJson("/api/models/" + encodeURIComponent(modelId) + "/", btn, "✅");
}

/**
 * Copy the raw API response (as-is) to the clipboard.
 * @param {HTMLElement} btn - The button that was clicked
 */
function copyAllJson(btn) {
    fetchAndCopyJson("/api/models/", btn, "✅ Copied");
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
