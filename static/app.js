"use strict";

var tg = window.Telegram && window.Telegram.WebApp;
var COUNTRIES = [
  ["RU", "Россия"], ["UA", "Украина"], ["BY", "Беларусь"], ["KZ", "Казахстан"],
  ["PL", "Польша"], ["UZ", "Узбекистан"], ["GE", "Грузия"], ["LT", "Литва"],
  ["DE", "Германия"], ["AE", "ОАЭ"]
];
var DEFAULT_NICHES = [
  { id: 0, title: "Барбершопы" }, { id: 1, title: "Салоны красоты" },
  { id: 6, title: "Маникюр и ногти" }, { id: 2, title: "Автосервисы" },
  { id: 3, title: "Стоматологии" }, { id: 4, title: "Фитнес и спортзалы" },
  { id: 7, title: "Кофейни и кафе" }, { id: 8, title: "Рестораны" },
  { id: 9, title: "Ветклиники" }, { id: 10, title: "Языковые и детские школы" },
  { id: 5, title: "Своя ниша" }
];
var CUSTOM_NICHE = 5;
var MODES = [["all", "Все"], ["none", "Без сайта"], ["weak", "Слабый сайт"], ["bot", "Нужен бот"]];
var NEED_NAMES = {
  site_bot: "Нужен сайт и Telegram-бот",
  site: "Нужен сайт",
  broken: "Сайт не работает — нужен новый",
  redesign: "Нужен редизайн сайта",
  weak: "Слабый сайт — нужно улучшить",
  bot: "Нормальный сайт, но нужен Telegram-бот"
};
var SITE_PILLS = { none: ["none", "Сайта нет"], broken: ["none", "Сайт не работает"], weak: ["weak", "Слабый сайт"], ok: ["ok", "Сайт есть"] };
var STATUS_NAMES = {
  "new": "Новый", "written": "Написал", "replied": "Ответил",
  "rejected": "Отказ", "client": "Клиент"
};
var FILTERS = [
  ["all", "Все"], ["new", "Новые"], ["written", "Написал"],
  ["replied", "Ответил"], ["rejected", "Отказ"], ["client", "Клиенты"]
];
var KINDS = [["first", "Первое"], ["short", "Короткое"], ["detailed", "Подробное"], ["call", "Звонок"], ["followup", "Повторное"]];
var TABS = [
  ["search", "Поиск", "search"], ["leads", "Лиды", "list"],
  ["scripts", "Скрипты", "doc"], ["stats", "Статистика", "chart"],
  ["faq", "Вопросы", "help"], ["admin", "Админ", "shield"]
];
var ADMIN_TABS = [["users", "Пользователи"], ["keys", "Ключи"], ["leads", "Все лиды"], ["overview", "Статистика"], ["blocked", "Чёрный список"], ["errors", "Ошибки"]];
var SUPPORT_TELEGRAM = "SUN9ISE";
var JOIN_URL = "https://t.me/m/KXcCg7quZGFh";
var NOT_FOUND = "не найдено";
var leads = [];
var S = {
  tab: "search", country: "RU", city: "", niche: 0, custom: "",
  flt: "all", count: 15, used: 0, limit: 70, filter: "all",
  admin: false, name: "", username: "", stats: {}, access: null, niches: DEFAULT_NICHES,
  users: [], editId: null, editVal: 70, loading: false,
  progress: null, requestSeq: 0, shown: 0, open: {},
  scriptNiche: 0, scripts: [], scriptEdit: null, scriptOpen: {},
  atab: "users", keys: [], adminLeads: [], adminQuery: "", overview: null, blocked: [], errors: null, userQuery: "",
  trialOffer: null, newKey: ""
};
var $ = function (selector) { return document.querySelector(selector); };
var esc = function (value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
};
var ic = function (name, cls) {
  return '<svg class="ic' + (cls ? " " + cls : "") + '" aria-hidden="true"><use href="#i-' + esc(name) + '"/></svg>';
};
var hap = function () {
  try {
    if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
  } catch (_) {}
};
var isTrial = function () { return S.access && S.access.plan === "trial"; };
var trialOver = function () { return isTrial() && S.access.searches_left <= 0; };
var remaining = function () {
  if (isTrial()) return S.access.searches_left > 0 ? S.access.trial_leads : 0;
  return Math.max(0, S.limit - S.used);
};
var countOptions = function (rest) {
  if (isTrial()) return rest > 0 ? [S.access.trial_leads] : [];
  var values = [15, 30, 50].filter(function (value) { return value <= rest; });
  if (rest > 0 && rest < 30 && values.indexOf(rest) < 0) values.push(rest);
  return values;
};
var nicheTitle = function (id) {
  var found = S.niches.filter(function (item) { return item.id === id; })[0];
  return found ? found.title : "";
};
var leadsToView = function (lead) {
  return {
    id: lead.id,
    name: lead.name || "Без названия",
    country: lead.country || "",
    city: lead.city || "",
    phone: lead.phone || "",
    site: lead.site || "none",
    url: lead.url || "",
    c: lead.c || {},
    reasons: Array.isArray(lead.reasons) ? lead.reasons : [],
    hot: Number(lead.hot) || 0,
    status: lead.status || "new",
    need: lead.need || "",
    explain: lead.explain || "",
    info: lead.info || {},
    niche: lead.niche || "",
    source: lead.source || ""
  };
};

function toast(message) {
  var node = $("#toast");
  node.textContent = String(message || "");
  node.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(function () { node.classList.remove("show"); }, 3200);
}

function api(path, options) {
  options = options || {};
  var headers = Object.assign({}, options.headers || {}, {
    "X-Init-Data": tg && tg.initData ? tg.initData : ""
  });
  if (options.body) headers["Content-Type"] = "application/json";
  return fetch(path, Object.assign({}, options, { headers: headers }))
    .then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var detail = data.detail;
          var text = detail;
          if (detail && typeof detail === "object" && !Array.isArray(detail)) text = detail.message;
          if (Array.isArray(detail)) text = "Проверьте введённые данные.";
          var error = new Error(text || ("Ошибка сервера: " + response.status));
          error.status = response.status;
          error.detail = detail;
          throw error;
        }
        return data;
      });
    });
}

function openLink(url) {
  try {
    if (tg && /^https:\/\/t\.me\//.test(url)) return tg.openTelegramLink(url);
    if (tg && /^https?:/.test(url)) return tg.openLink(url);
  } catch (_) {}
  window.open(url, "_blank", "noopener");
}

function copyText(text) {
  var done = function () { toast("Скопировано."); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(function () { fallbackCopy(text); });
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  var area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try { document.execCommand("copy"); toast("Скопировано."); } catch (_) { toast("Выделите текст и скопируйте вручную."); }
  document.body.removeChild(area);
}

function loadMe() {
  return api("/api/me").then(function (me) {
    S.name = me.name || "";
    S.username = me.username || "";
    S.admin = Boolean(me.is_admin);
    S.limit = Number(me.limit) || 0;
    S.used = Number(me.used) || 0;
    S.access = me.access || null;
    if (me.access && me.access.join) JOIN_URL = me.access.join;
    if (me.access && me.access.contact) SUPPORT_TELEGRAM = me.access.contact;
    if (Array.isArray(me.niches) && me.niches.length) S.niches = me.niches;
    if (S.tab === "admin" && !S.admin) S.tab = "search";
    return me;
  });
}

function loadLeads() {
  return api("/api/leads?status=all&limit=1000").then(function (data) {
    leads = (data.leads || []).map(leadsToView);
    return leads;
  });
}

function loadStats() {
  return api("/api/stats").then(function (stats) {
    S.stats = stats || {};
    return S.stats;
  });
}

function loadScripts() {
  return api("/api/scripts?niche=" + encodeURIComponent(S.scriptNiche)).then(function (data) {
    S.scripts = data.scripts || [];
    return S.scripts;
  });
}

function refreshAll() {
  return loadMe().then(function () {
    return Promise.all([loadLeads(), loadStats()]);
  }).then(function () {
    if (S.tab === "admin" && S.admin) return loadAdmin();
  }).then(function () { render(); });
}

/* ---------- Поиск ---------- */

function accessCard() {
  if (trialOver()) return trialOfferCard(S.access.trial_message);
  if (isTrial()) {
    return '<div class="card access"><div class="row"><span>Пробный доступ</span><b>' +
      S.access.searches_left + " " + plural(S.access.searches_left, "запрос", "запроса", "запросов") +
      '</b></div><p class="muted small">До ' + S.access.trial_leads +
      ' лидов за запрос. Дальше — в команде C&amp;C Family или по ключу.</p></div>';
  }
  var rest = remaining();
  var usedPercent = S.limit ? Math.min(100, Math.round(S.used / S.limit * 100)) : 0;
  return '<div class="card"><div class="row"><span>Лимит на сегодня</span><b>' +
    S.used + " / " + S.limit + '</b></div><div class="bar"><i style="width:' +
    usedPercent + '%"></i></div><p class="muted small">Осталось ' + rest +
    '. Обновление по времени сервера.</p></div>';
}

function trialOfferCard(message) {
  var text = message || ("Пробный доступ закончился.\nЧтобы продолжить получать лиды и пользоваться Parser C&C, вступите в команду C&C Family,\nподробности можно узнать у @" + SUPPORT_TELEGRAM + ".");
  return '<div class="card offer"><p>' + esc(text) + '</p><div class="btns">' +
    '<a class="btn main" data-ext href="' + esc(JOIN_URL) + '" target="_blank" rel="noopener">' + ic("users") + "Вступить в команду</a>" +
    '<a class="btn" data-ext href="https://t.me/' + esc(SUPPORT_TELEGRAM) + '" target="_blank" rel="noopener">' + ic("plus") + "Докупить запросы</a>" +
    '<a class="btn" data-ext href="https://t.me/' + esc(SUPPORT_TELEGRAM) + '" target="_blank" rel="noopener">' + ic("send") + "Написать @" + esc(SUPPORT_TELEGRAM) + "</a></div>" +
    '<form id="key-form" class="keyform"><input name="code" placeholder="Ключ доступа CC-…" autocomplete="off" maxlength="64" aria-label="Ключ доступа">' +
    '<button class="btn" type="submit">' + ic("key") + "Ввести</button></form></div>";
}

function plural(n, one, few, many) {
  var mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

function vSearch() {
  var rest = remaining();
  var options = countOptions(rest);
  if (options.indexOf(S.count) < 0) S.count = options[0] || 0;
  var hello = S.name ? "Привет, " + esc(S.name) : "Привет";
  var cityValue = S.city ? esc(S.city) : "";
  return '<section class="screen"><div class="hello">' + hello +
    '<small>Найди бизнесы, которым может быть нужен сайт или ТГ-бот</small></div>' +
    accessCard() +
    '<button class="fire" data-act="demand">' + ic("fire") +
    '<span>Какие ниши сейчас требуют сайт/бот?<small>Статистика по реальным проверкам парсера</small></span>' +
    ic("chev", "chev") + "</button>" +
    '<h3>Страна</h3><select id="country" aria-label="Страна">' +
    COUNTRIES.map(function (country) {
      return '<option value="' + country[0] + '"' +
        (S.country === country[0] ? " selected" : "") + '>' +
        country[0] + " — " + esc(country[1]) + "</option>";
    }).join("") +
    '</select><h3>Город или регион <span class="optional">необязательно</span></h3>' +
    '<input id="city" value="' + cityValue +
    '" placeholder="Пусто — искать по всей стране" autocomplete="off" maxlength="80">' +
    '<p class="muted small location-hint">С городом поиск точнее и подключается больше источников.</p>' +
    '<h3>Ниша</h3><div class="chips">' +
    S.niches.map(function (item) {
      return '<button class="chip ' + (S.niche === item.id ? "on" : "") +
        '" data-act="niche" data-v="' + item.id + '">' + esc(item.title) + "</button>";
    }).join("") + "</div>" +
    (S.niche === CUSTOM_NICHE
      ? '<input id="cn" value="' + esc(S.custom) +
        '" placeholder="Слово из названия, например шиномонтаж" maxlength="80">'
      : "") +
    '<h3>Кого искать</h3><div class="seg">' +
    MODES.map(function (item) {
      return '<button class="' + (S.flt === item[0] ? "on" : "") +
        '" data-act="flt" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>" +
    '<h3>Сколько</h3><div class="seg">' +
    (options.length
      ? options.map(function (value) {
        return '<button class="' + (S.count === value ? "on" : "") +
          '" data-act="count" data-v="' + value + '">' + value +
          (!isTrial() && [15, 30, 50].indexOf(value) < 0 ? " · остаток" : "") + "</button>";
      }).join("")
      : '<button disabled>' + (isTrial() ? "Пробный доступ закончился" : "Лимит исчерпан") + "</button>") +
    '</div><button class="cta" data-act="go" ' +
    (rest > 0 && S.count && !S.loading ? "" : "disabled") +
    '>Найти ' + (S.count || "") + " бизнесов</button></section>";
}

var STAGES = [
  "Собираю организации из открытых карт…",
  "Убираю дубли и уже выданные бизнесы…",
  "Открываю сайты и проверяю их…",
  "Проверяю Telegram, запись и контакты…",
  "Считаю приоритет каждого лида…"
];

function progressPercent(progress) {
  var maxChecks = progress.total * 6 + 40;
  var byChecks = progress.checked / maxChecks;
  var byFound = progress.found / Math.max(1, progress.total) * 0.92;
  return Math.min(94, Math.max(6, Math.round(Math.max(byChecks, byFound) * 100)));
}

function loadingView() {
  var progress = S.progress || { found: 0, checked: 0, total: 1 };
  return '<section class="screen center"><div class="beat"><i class="bird"></i></div>' +
    '<h2>Ищу и проверяю бизнесы</h2><p class="muted" id="pt">' +
    "Найдено " + progress.found + " из " + progress.total +
    " · проверено " + progress.checked + '</p><div class="glow"><i id="pb" style="width:' + Math.max(6, S.shown) +
    '%"></i></div><p class="muted small stage" id="pstage">' + esc(STAGES[0]) + "</p>" +
    '<p class="muted small">Каждый лид проверяется вживую, поэтому поиск занимает 1–3 минуты.</p></section>';
}

function updateLoading() {
  var progress = S.progress;
  if (!progress) return;
  var target = progressPercent(progress);
  S.shown = Math.max(S.shown, target);
  var text = $("#pt");
  var bar = $("#pb");
  var stage = $("#pstage");
  if (text) text.textContent = "Найдено " + progress.found + " из " + progress.total + " · проверено " + progress.checked;
  if (bar) bar.style.width = S.shown + "%";
  if (stage) {
    var index = progress.checked === 0 ? (S.shown < 10 ? 0 : 1) : progress.found ? 4 : (progress.checked % 2 ? 2 : 3);
    stage.textContent = STAGES[Math.min(STAGES.length - 1, index)];
  }
}

function go() {
  if (S.loading) return;
  var count = Number(S.count);
  if (!count || count > remaining()) {
    toast(isTrial() ? "Пробный доступ закончился." : "Доступно лидов на сегодня: " + remaining() + ".");
    return;
  }
  if (S.niche === CUSTOM_NICHE && !S.custom.trim()) {
    toast("Введите слово для своей ниши.");
    return;
  }

  var requestNumber = ++S.requestSeq;
  var payload = {
    country: S.country,
    city: S.city.trim(),
    niche: S.niche,
    custom: S.custom.trim(),
    flt: S.flt,
    count: count
  };
  S.loading = true;
  S.shown = 4;
  S.progress = { found: 0, checked: 0, total: count };
  render();
  var creep = setInterval(function () {
    if (!S.loading) return clearInterval(creep);
    if (S.shown < 88) { S.shown += 0.6; updateLoading(); }
  }, 1500);

  function stop(message, tab) {
    clearInterval(creep);
    S.loading = false;
    S.tab = tab || "search";
    render();
    if (message) toast(message);
  }

  api("/api/search", { method: "POST", body: JSON.stringify(payload) })
    .then(function (result) {
      S.progress.total = Number(result.count) || count;
      function poll() {
        if (requestNumber !== S.requestSeq) return;
        api("/api/jobs/" + encodeURIComponent(result.job_id)).then(function (job) {
          S.progress = {
            found: Number(job.found) || 0,
            checked: Number(job.checked) || 0,
            total: Number(job.total) || count
          };
          updateLoading();
          if (job.status === "done") {
            S.shown = 100;
            updateLoading();
            S.trialOffer = job.trial_over || null;
            return Promise.all([loadMe(), loadLeads(), loadStats()]).then(function () {
              setTimeout(function () {
                stop("Поиск завершён. Новых лидов: " + (job.found || 0) + ".", "leads");
                S.filter = "all";
                if (S.trialOffer) showTrialOffer(S.trialOffer);
              }, 500);
            });
          }
          if (job.status === "error") {
            stop(job.error || "Поиск завершился с ошибкой.");
            return;
          }
          setTimeout(poll, 1200);
        }).catch(function (error) { stop(error.message); });
      }
      poll();
    })
    .catch(function (error) {
      if (error.detail && error.detail.code === "trial_over") {
        stop("");
        loadMe().then(function () { render(); showTrialOffer(error.detail); });
        return;
      }
      stop(error.message);
    });
}

function showTrialOffer(detail) {
  openSheet('<div class="top"><h2>C&amp;C Family</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' +
    ic("x") + "</button></div>" + trialOfferCard(detail && detail.message));
}

/* ---------- Ниши со спросом ---------- */

function showDemand() {
  openSheet('<div class="top"><h2>Ниши, которым нужен сайт или бот</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' +
    ic("x") + '</button></div><div class="dots"><i></i><i></i><i></i></div>');
  api("/api/demand?country=" + encodeURIComponent(S.country)).then(function (data) {
    var items = data.items || [];
    var body;
    if (!items.length) {
      body = '<div class="card"><p>Пока мало данных для честной статистики.</p><p class="muted small">Статистика появится, когда парсер проверит хотя бы ' +
        esc(data.min_sample || 30) + " бизнесов в нише в выбранной стране. Цифры берутся только из реальных проверок, ничего не досчитывается.</p></div>";
    } else {
      body = '<p class="muted small">По реальным проверкам парсера за последние месяцы, страна ' + esc(S.country) +
        '. Чем больше бизнесов без сайта и бота, тем выше спрос.</p><div class="card">' +
        items.map(function (item) {
          var id = (S.niches.filter(function (n) { return n.title === item.niche; })[0] || {}).id;
          return '<div class="dm"><div class="row"><b>' + esc(item.niche) + '</b><span class="badge">' + esc(item.total) +
            ' проверено</span></div><div class="meta">' +
            "<span>Без сайта <em>" + item.no_site + "%</em></span>" +
            "<span>Слабый сайт <em>" + item.weak + "%</em></span>" +
            "<span>Без Telegram-бота <em>" + item.no_bot + "%</em></span>" +
            "<span>Без онлайн-записи <em>" + item.no_booking + "%</em></span>" +
            "<span>Средний приоритет <em>" + item.avg_priority + "</em></span></div>" +
            (id != null ? '<button class="ghost" data-act="pickniche" data-v="' + id + '">Искать в этой нише</button>' : "") +
            "</div>";
        }).join("") + "</div>";
    }
    setSheetBody('<div class="top"><h2>Ниши, которым нужен сайт или бот</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' +
      ic("x") + "</button></div>" + body);
  }).catch(function (error) {
    closeSheet();
    toast(error.message);
  });
}

/* ---------- Лиды ---------- */

function safeHttpLink(value) {
  try {
    var url = new URL(String(value || ""));
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch (_) { return ""; }
}

function tgName(value) {
  var name = String(value || "").replace(/^@/, "");
  return /^[A-Za-z][A-Za-z0-9_]{3,31}$/.test(name) && !/^(https?|www)$/i.test(name) ? name : "";
}

function contacts(lead) {
  var contact = lead.c || {};
  var output = [];
  var telegram = tgName(contact.tg);
  if (telegram) output.push('<a href="https://t.me/' + telegram + '" target="_blank" rel="noopener">Telegram</a>');
  var whatsapp = String(contact.wa || "").replace(/\D/g, "");
  if (whatsapp.length >= 8 && whatsapp.length <= 15) {
    output.push('<a href="https://wa.me/' + whatsapp + '" target="_blank" rel="noopener">WhatsApp</a>');
  }
  var vk = String(contact.vk || contact.vkg || "").replace(/^@/, "");
  if (/^[A-Za-z0-9_.]{2,64}$/.test(vk) && !/^(https?|www)$/i.test(vk) && !/^\d+$/.test(vk)) {
    output.push('<a href="https://vk.com/' + encodeURIComponent(vk) + '" target="_blank" rel="noopener">VK</a>');
  }
  var instagram = String(contact.ig || "");
  var instagramUrl = safeHttpLink(instagram) ||
    (/^[A-Za-z0-9_.]{1,30}$/.test(instagram) ? "https://www.instagram.com/" + encodeURIComponent(instagram.replace(/^@/, "")) : "");
  if (instagramUrl) output.push('<a href="' + esc(instagramUrl) + '" target="_blank" rel="noopener">Instagram</a>');
  var facebookUrl = safeHttpLink(contact.fb || "");
  if (facebookUrl) output.push('<a href="' + esc(facebookUrl) + '" target="_blank" rel="noopener">Facebook</a>');
  var email = String(contact.email || "");
  if (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) output.push('<a href="mailto:' + encodeURIComponent(email) + '">Email</a>');
  var viber = String(contact.vb || "").replace(/\D/g, "");
  if (viber.length >= 8 && viber.length <= 15) output.push('<a href="viber://chat?number=%2B' + viber + '">Viber</a>');
  var map = safeHttpLink(contact.map || "");
  if (map) output.push('<a href="' + esc(map) + '" target="_blank" rel="noopener">Карта</a>');
  if (lead.site === "weak" || lead.site === "ok") {
    var site = safeHttpLink(lead.url || contact.site || "");
    if (site) output.push('<a class="site" href="' + esc(site) + '" target="_blank" rel="noopener">' + ic("link") + "Сайт</a>");
  }
  return output.length ? '<div class="ct">' + output.join("") + "</div>" : "";
}

function yesNo(value, yes, no) {
  if (value === true) return yes || "есть";
  if (value === false) return no || "нет";
  return '<span class="no">не удалось проверить</span>';
}

function infoRow(label, value) {
  var empty = value == null || value === "";
  return "<div><span>" + label + "</span><em" + (empty ? ' class="no"' : "") + ">" +
    (empty ? NOT_FOUND : value) + "</em></div>";
}

function leadDetails(lead) {
  var info = lead.info || {};
  var c = lead.c || {};
  var hasSite = lead.site === "weak" || lead.site === "ok";
  var siteUrl = safeHttpLink(lead.url || c.site || "");
  var sources = (info.sources || []).map(function (item) {
    var url = safeHttpLink(item.u);
    return url ? '<a data-ext href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(item.t) + "</a>" : esc(item.t);
  }).join(", ");
  var rows = [
    infoRow("Ниша", esc(lead.niche || info.niche || "")),
    infoRow("Адрес", esc(c.address || info.address || "")),
    infoRow("Телефон", esc(lead.phone)),
    infoRow("Email", esc(c.email || "")),
    infoRow("Сайт", lead.site === "none" ? "нет" :
      lead.site === "broken" ? "не открывается" + (lead.url ? " (" + esc(lead.url.replace(/^https?:\/\//, "").replace(/\/$/, "")) + ")" : "") :
      siteUrl ? '<a data-ext href="' + esc(siteUrl) + '" target="_blank" rel="noopener">' + esc(siteUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")) + "</a>" : ""),
    infoRow("Telegram", tgName(c.tg) ? "@" + esc(tgName(c.tg)) : ""),
    infoRow("Telegram-бот", info.tg_bot ? esc(info.tg_bot) : "не найден"),
    infoRow("ВКонтакте", esc(c.vk || c.vkg || "")),
    infoRow("Instagram", esc(c.ig || "")),
    infoRow("Часы работы", esc(info.hours || "")),
    infoRow("Рейтинг", info.rating ? esc(info.rating) : ""),
    infoRow("Отзывов", info.reviews ? esc(info.reviews) : "")
  ];
  if (hasSite) {
    rows.push(
      infoRow("Онлайн-запись", info.booking ? esc(info.booking) : "не найдена"),
      infoRow("Форма заявки", yesNo(info.form)),
      infoRow("HTTPS", yesNo(info.https)),
      infoRow("Мобильная версия", yesNo(info.mobile)),
      infoRow("Скорость", info.speed != null ? esc(info.speed) + " с" : ""),
      infoRow("Актуальность", info.actual === true ? "обновлялся недавно" + (info.year ? " (© " + esc(info.year) + ")" : "") :
        info.actual === false ? "давно не обновлялся (© " + esc(info.year) + ")" : '<span class="no">не удалось проверить</span>')
    );
  }
  rows.push(infoRow("Источник", sources));
  return '<div class="info">' + rows.join("") + "</div>";
}

function leadCard(lead, index) {
  var status = lead.status || "new";
  var phone = String(lead.phone || "").trim();
  var dialable = phone.replace(/[^\d+]/g, "");
  var pill = SITE_PILLS[lead.site] || SITE_PILLS.none;
  var open = Boolean(S.open[lead.id]);
  var why = lead.explain || "";
  return '<article class="card lead" style="--i:' + index + '">' +
    '<div class="row"><b>' + esc(lead.name) + '</b><button class="hot" data-act="tip" aria-label="Приоритет">' +
    "<b>" + esc(lead.hot) + "</b><small>приоритет</small>" +
    '<span class="tip">' + esc(why || "Балл 0–100 для сортировки: учитывает сайт, бот, запись и контакты. Это не вероятность сделки.") + "</span></button></div>" +
    '<p class="muted small">' + esc(lead.country) + " · " + esc(lead.city) +
    (lead.niche ? " · " + esc(lead.niche) : "") + "</p>" +
    '<div class="row g"><span class="pill ' + pill[0] + '">' + pill[1] + "</span>" +
    (dialable ? '<a class="tel" href="tel:' + esc(dialable) + '">' + ic("phone") + esc(phone) + "</a>" : '<span class="tel"></span>') + "</div>" +
    (lead.need && NEED_NAMES[lead.need] ? '<span class="need">' + esc(NEED_NAMES[lead.need]) + "</span>" : "") +
    (why ? '<p class="why">' + esc(why) + "</p>" : "") +
    contacts(lead) +
    (open ? leadDetails(lead) : "") +
    '<div class="acts"><button data-act="more" data-id="' + encodeURIComponent(lead.id) + '">' + ic("info") +
    (open ? "Скрыть" : "Подробнее") + '</button><button class="gen" data-act="leadscript" data-id="' +
    encodeURIComponent(lead.id) + '">' + ic("spark") + "Сгенерировать скрипт</button></div>" +
    '<div class="st">' + ["written", "replied", "rejected", "client"].map(function (key) {
      return '<button class="' + (status === key ? "on" : "") +
        '" data-act="status" data-id="' + encodeURIComponent(lead.id) +
        '" data-v="' + key + '">' + STATUS_NAMES[key] + "</button>";
    }).join("") + "</div></article>";
}

function vLeads() {
  var filtered = leads.filter(function (lead) {
    return S.filter === "all" || lead.status === S.filter;
  });
  return '<section class="screen"><div class="top"><h2>Лиды <small>' +
    esc(S.stats.found == null ? leads.length : S.stats.found) +
    '</small></h2><button class="icon-btn" data-act="export" aria-label="Скачать Excel">' +
    ic("download") + "</button></div>" +
    '<div class="chips scroll">' + FILTERS.map(function (item) {
      return '<button class="chip ' + (S.filter === item[0] ? "on" : "") +
        '" data-act="filter" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>" +
    (isTrial() && leads.length ? trialMini() : "") +
    (filtered.length
      ? filtered.map(leadCard).join("")
      : '<div class="empty">' + ic("list") + "<p>" +
        (leads.length ? "В этом фильтре пока пусто" : "Здесь пока пусто") + "</p></div>") +
    (leads.length >= 1000
      ? '<p class="muted small" style="text-align:center">Показаны последние 1000 лидов. Полный список можно выгрузить в Excel.</p>'
      : "") +
    (leads.length ? '<p class="muted small srcnote">Данные организаций: <a data-ext href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>, сайты самих компаний.</p>' : "") +
    "</section>";
}

function trialMini() {
  if (!trialOver()) return "";
  return '<div class="card offer"><div class="row"><b>Пробный доступ закончился</b></div>' +
    '<p class="muted small">Лиды остаются у вас. Чтобы искать дальше — вступите в C&amp;C Family.</p>' +
    '<div class="btns"><button class="btn main" data-act="offer">Подробнее</button></div></div>';
}

function generateLeadScript(lead, kind) {
  kind = kind || "first";
  var head = '<div class="top"><h2>Скрипт для «' + esc(lead.name) + '»</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' +
    ic("x") + '</button></div><div class="chips scroll kinds">' + KINDS.map(function (item) {
      return '<button class="chip ' + (kind === item[0] ? "on" : "") + '" data-act="leadkind" data-id="' +
        encodeURIComponent(lead.id) + '" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>";
  openSheet(head + '<div class="dots"><i></i><i></i><i></i></div><p class="muted small" style="text-align:center">Пишу скрипт по данным этого бизнеса…</p>');
  api("/api/leads/" + encodeURIComponent(lead.id) + "/script", {
    method: "POST", body: JSON.stringify({ kind: kind })
  }).then(function (result) {
    S.sheetText = result.text || "";
    setSheetBody(head + '<div class="card"><pre id="gen-text">' + esc(result.text) + "</pre></div>" +
      (result.note ? '<p class="muted small">' + esc(result.note) + "</p>" : '<p class="muted small">Сгенерировано нейросетью по реальным данным лида. Перед отправкой прочитайте и при необходимости поправьте.</p>') +
      '<div class="tools"><button class="main" data-act="copygen">' + ic("copy") + "Копировать</button>" +
      '<button data-act="leadkind" data-id="' + encodeURIComponent(lead.id) + '" data-v="' + kind + '">' + ic("spark") + "Ещё вариант</button>" +
      '<button data-act="savegen" data-v="' + kind + '" data-n="' + esc(lead.niche) + '">' + ic("doc") + "Сохранить в мои скрипты</button></div>");
  }).catch(function (error) {
    closeSheet();
    toast(error.message);
  });
}

/* ---------- Скрипты ---------- */

function vScripts() {
  var niches = S.niches.filter(function (item) { return item.id !== CUSTOM_NICHE; });
  var list = S.scripts || [];
  return '<section class="screen"><h2>Скрипты</h2>' +
    '<div class="card lead-in"><p>Готовые тексты для первого сообщения, звонка и повторного касания по каждой нише. ' +
    "Скопируйте, поправьте под себя или сгенерируйте новый вариант. В карточке лида кнопка «Сгенерировать скрипт» пишет текст под конкретный бизнес по его реальным данным.</p>" +
    '<p class="muted small" style="margin-top:6px">[Название] и [Ваше имя] замените на свои данные.' +
    (S.admin ? " Вы администратор: правка стандартного скрипта меняет его для всех." : "") + "</p></div>" +
    '<div class="chips scroll">' + niches.map(function (item) {
      return '<button class="chip ' + (S.scriptNiche === item.id ? "on" : "") + '" data-act="sniche" data-v="' + item.id + '">' + esc(item.title) + "</button>";
    }).join("") + "</div>" +
    '<div class="card">' + (list.length ? list.map(scriptItem).join("") : '<div class="dots"><i></i><i></i><i></i></div>') + "</div>" +
    '<div class="card"><h3>Сгенерировать новый</h3><p class="muted small">Нейросеть напишет новый вариант для ниши «' +
    esc(nicheTitle(S.scriptNiche)) + '».</p><div class="tools">' + KINDS.map(function (item) {
      return '<button data-act="genniche" data-v="' + item[0] + '">' + ic("spark") + item[1] + "</button>";
    }).join("") + "</div></div></section>";
}

function scriptItem(item) {
  var editing = S.scriptEdit === item.id;
  var open = Boolean(S.scriptOpen[item.id]);
  var kindName = (KINDS.filter(function (k) { return k[0] === item.kind; })[0] || [0, item.kind])[1];
  if (editing) {
    return '<div class="scr"><form id="script-form" data-id="' + item.id + '" data-kind="' + esc(item.kind) + '" class="form">' +
      '<input name="title" value="' + esc(item.title) + '" maxlength="80" required aria-label="Название">' +
      '<textarea name="body" rows="9" maxlength="4000" required>' + esc(item.body) + "</textarea>" +
      '<div class="tools"><button class="main" type="submit">Сохранить</button><button type="button" data-act="scancel">Отмена</button></div>' +
      (!item.own && !S.admin ? '<p class="muted small">Сохранится ваша копия, стандартный скрипт останется.</p>' : "") +
      "</form></div>";
  }
  return '<div class="scr"><div class="row"><b>' + esc(item.title) + '</b><span class="tag">' + esc(item.own ? "мой · " + kindName : kindName) + "</span></div>" +
    '<pre class="' + (open ? "" : "cut") + '" data-act="sopen" data-id="' + item.id + '">' + esc(item.body) + "</pre>" +
    '<div class="tools"><button class="main" data-act="scopy" data-id="' + item.id + '">' + ic("copy") + "Копировать</button>" +
    '<button data-act="sedit" data-id="' + item.id + '">' + ic("edit") + "Изменить</button>" +
    (!open ? '<button data-act="sopen" data-id="' + item.id + '">Читать полностью</button>' : "") +
    (item.own || S.admin ? '<button data-act="sdel" data-id="' + item.id + '">' + ic("trash") + "Удалить</button>" : "") +
    "</div></div>";
}

function generateNicheScript(kind) {
  var title = nicheTitle(S.scriptNiche);
  var head = '<div class="top"><h2>Новый скрипт: ' + esc(title) + '</h2><button class="icon-btn" data-act="close" aria-label="Закрыть">' + ic("x") + "</button></div>";
  openSheet(head + '<div class="dots"><i></i><i></i><i></i></div>');
  api("/api/scripts/generate", {
    method: "POST", body: JSON.stringify({ niche: S.scriptNiche, kind: kind })
  }).then(function (result) {
    S.sheetText = result.text || "";
    setSheetBody(head + '<div class="card"><pre>' + esc(result.text) + "</pre></div>" +
      (result.note ? '<p class="muted small">' + esc(result.note) + "</p>" : "") +
      '<div class="tools"><button class="main" data-act="copygen">' + ic("copy") + "Копировать</button>" +
      '<button data-act="genniche" data-v="' + kind + '">' + ic("spark") + "Ещё вариант</button>" +
      '<button data-act="savegen" data-v="' + kind + '" data-n="' + esc(title) + '">' + ic("doc") + "Сохранить</button></div>");
  }).catch(function (error) { closeSheet(); toast(error.message); });
}

function saveGenerated(kind, nicheName) {
  var niche = (S.niches.filter(function (item) { return item.title === nicheName; })[0] || {}).id;
  if (niche == null || niche === CUSTOM_NICHE) niche = S.scriptNiche;
  var kindName = (KINDS.filter(function (k) { return k[0] === kind; })[0] || [0, "Скрипт"])[1];
  api("/api/scripts", {
    method: "POST",
    body: JSON.stringify({ niche: niche, kind: kind, title: kindName + " — мой вариант", body: S.sheetText || "" })
  }).then(function () {
    toast("Сохранено во вкладке «Скрипты».");
    if (S.scriptNiche === niche) loadScripts().then(function () { if (S.tab === "scripts") render(true); });
  }).catch(function (error) { toast(error.message); });
}

/* ---------- Статистика и FAQ ---------- */

function vStats() {
  var stats = S.stats || {};
  var total = Number(stats.found) || 0;
  var contacted = Number(stats.contacted) || 0;
  var replied = Number(stats.replied) || 0;
  var clients = Number(stats.clients) || 0;
  var rows = [["Найдено", total], ["Связались", contacted], ["Ответили", replied], ["Клиенты", clients]];
  var percentage = function (value) { return total ? Math.round(value / total * 100) : 0; };
  return '<section class="screen"><h2>Статистика</h2><div class="grid">' +
    rows.map(function (row) {
      return '<div class="card tile"><small class="muted">' + row[0] +
        '</small><b class="num" data-to="' + row[1] + '">' + row[1] + "</b></div>";
    }).join("") + '</div><div class="card"><h3>Воронка</h3>' +
    rows.map(function (row) {
      return '<div class="fn"><span>' + row[0] + '</span><div class="bar"><i style="width:' +
        percentage(row[1]) + '%"></i></div><em>' + percentage(row[1]) + "%</em></div>";
    }).join("") + '</div><div class="card"><div class="row"><span>Ответили от найденных</span><b>' +
    percentage(replied) + '%</b></div><div class="row g"><span>Клиенты от найденных</span><b>' +
    percentage(clients) + "%</b></div></div>" +
    '<p class="muted small">Статистика показывает только отмеченные вручную результаты. Она не предсказывает будущие продажи.</p></section>';
}

function faqItem(question, answer) {
  return "<details><summary>" + question + "</summary><p>" + answer + "</p></details>";
}

function vFaq() {
  var keys = [
    ["Откуда берутся лиды", "Из открытых карт OpenStreetMap (через Overpass и Geoapify) и с сайтов самих компаний. Каждый бизнес проверяется вживую: открывается сайт, ищутся онлайн-запись, форма заявки, Telegram и контакты."],
    ["Один лид — один человек", "Каждый найденный бизнес закрепляется за одним пользователем навсегда. Его не получит никто другой, и вам он не попадётся второй раз — даже если у него другое название, формат номера или он есть в нескольких источниках."],
    ["Пробный доступ", "У каждого есть 1 пробный запрос до 10 лидов. Если поиск ничего не нашёл, запрос не списывается. Дальше — в команде C&C Family, по ключу доступа или с докупленными запросами."],
    ["Ключ доступа", "Если администратор выдал вам ключ, введите его на главной после окончания пробного доступа или отправьте боту: /key КОД."],
    ["Режимы поиска", "«Без сайта» — сайта нет или он не открывается. «Слабый сайт» — сайт есть, но с проблемами. «Нужен бот» — нормальный сайт без Telegram-бота. «Все» — любые подходящие."],
    ["Приоритет", "Балл 0–100 для сортировки. Нажмите на него — увидите объяснение: что с сайтом, какие есть контакты, найден ли Telegram-бот и онлайн-запись. Это не вероятность сделки."],
    ["«Не найдено» и «не удалось проверить»", "Парсер ничего не придумывает. Если данных нет в источниках — пишет «не найдено». Если сайт не дал себя проверить — «не удалось проверить». Бизнесы с большим количеством непроверенных данных в выдачу не попадают."],
    ["Контакты", "Телефоны проверяются по правилам номеров страны. Ссылки Telegram проверяются: если аккаунта нет, ссылка не показывается. Лиды без телефона и мессенджеров в выдачу не попадают."],
    ["Скрипты", "Во вкладке «Скрипты» — готовые тексты по нишам: первое сообщение, короткое, подробное, звонок и повторное. В карточке лида кнопка «Сгенерировать скрипт» пишет текст под конкретный бизнес."],
    ["Какие ниши сейчас требуют сайт", "Кнопка с огоньком на главной показывает статистику по реальным проверкам: сколько бизнесов в нише без сайта, со слабым сайтом, без бота и записи. Если данных мало — статистика не показывается."],
    ["Статусы и Excel", "Отмечайте: Написал, Ответил, Отказ или Клиент. Кнопка загрузки на вкладке «Лиды» пришлёт Excel-файл в чат с ботом."],
    ["Лимит", "Для участников — сколько лидов можно получить сегодня. Успешный поиск расходует число найденных лидов, при ошибке лимит возвращается."],
    ["Источники данных", "Данные организаций: © OpenStreetMap contributors (лицензия ODbL), Geoapify, а также опубликованные контакты на сайтах самих компаний. Карты иногда устаревают — перед сообщением полезно открыть карточку на карте."]
  ];
  return '<section class="screen"><h2>Вопросы</h2>' +
    '<div class="card"><h3>Как пользоваться</h3><p>Выберите страну, город, нишу и режим, запустите поиск. Откройте карточку лида, посмотрите, почему у него такой приоритет, сгенерируйте скрипт и напишите. Отмечайте результат статусами.</p></div>' +
    '<div class="card faq"><h3>Частые вопросы</h3>' +
    keys.map(function (item) { return faqItem(esc(item[0]), esc(item[1])); }).join("") +
    "</div><a class=\"contact\" data-ext href=\"https://t.me/" + esc(SUPPORT_TELEGRAM) +
    "\" target=\"_blank\" rel=\"noopener\">" + ic("send") +
    "Написать @" + esc(SUPPORT_TELEGRAM) + "</a>" +
    '<p class="muted small" style="text-align:center;margin:10px 0 4px">Поддержка</p></section>';
}

/* ---------- Админ ---------- */

function loadAdmin() {
  if (!S.admin) return Promise.reject(new Error("Только для администратора."));
  var loaders = {
    users: function () { return api("/api/admin/users").then(function (d) { S.users = d.users || []; }); },
    keys: function () { return api("/api/admin/keys").then(function (d) { S.keys = d.keys || []; }); },
    leads: function () {
      return api("/api/admin/leads?q=" + encodeURIComponent(S.adminQuery)).then(function (d) { S.adminLeads = (d.leads || []).map(function (l) { var v = leadsToView(l); v.owner = l.owner; return v; }); });
    },
    overview: function () { return api("/api/admin/overview").then(function (d) { S.overview = d; }); },
    blocked: function () { return api("/api/admin/blocked").then(function (d) { S.blocked = d.items || []; }); },
    errors: function () { return api("/api/admin/overview").then(function (d) { S.errors = d.errors; S.overview = d; }); }
  };
  return (loaders[S.atab] || loaders.users)();
}

function userRow(user) {
  var editing = S.editId === user.id;
  var badge = user.banned ? '<span class="badge b">Бан</span>' :
    user.plan === "member" ? '<span class="badge m">' + (user.is_admin ? "Владелец" : "Участник") + "</span>" :
    '<span class="badge">Проба ' + user.trial_used + "/" + (1 + Number(user.bonus || 0)) + "</span>";
  return '<div class="usr"><div class="row"><b>' + esc(user.n) + "</b>" + badge + "</div>" +
    '<p class="muted small">ID ' + esc(user.id) + (user.plan === "member" ? " · сегодня " + user.t + "/" + user.lim : " · осталось запросов " + esc(user.trial_left)) +
    " · лидов " + user.f + " · клиенты " + user.k + (user.bonus ? " · бонус " + user.bonus : "") + "</p>" +
    (user.is_admin ? "" : '<div class="urow">' +
      '<button data-act="access" data-id="' + user.id + '" data-v="' + (user.approved ? "0" : "1") + '">' + (user.approved ? "Закрыть доступ" : "Выдать доступ") + "</button>" +
      '<button data-act="edit" data-id="' + user.id + '">' + ic("edit") + " Лимит</button>" +
      '<button data-act="bonus" data-id="' + user.id + '" data-v="1">+1 запрос</button>' +
      '<button data-act="bonus" data-id="' + user.id + '" data-v="5">+5</button>' +
      '<button data-act="ban" data-id="' + user.id + '" data-v="' + (user.banned ? "0" : "1") + '">' + (user.banned ? "Разбанить" : "Забанить") + "</button></div>") +
    (editing
      ? '<div class="edit"><div class="row"><span class="muted small">Дневной лимит: <b>' +
        S.editVal + '</b></span><div class="step"><button data-act="limd" data-v="-10" aria-label="Меньше">−</button>' +
        '<button data-act="limd" data-v="10" aria-label="Больше">+</button></div></div>' +
        '<div class="chips">' + [0, 70, 100, 150, 200, 500].map(function (value) {
          return '<button class="chip ' + (S.editVal === value ? "on" : "") + '" data-act="limset" data-v="' + value + '">' + value + "</button>";
        }).join("") + '</div><div class="row g"><button class="ghost" data-act="limcancel">Отмена</button><button class="ghost go" data-act="limsave">Сохранить</button></div></div>'
      : "") + "</div>";
}

function adminUsers() {
  var query = S.userQuery.trim().toLowerCase();
  var users = (S.users || []).filter(function (user) {
    return !query || String(user.n).toLowerCase().indexOf(query) >= 0 || String(user.id).indexOf(query) >= 0;
  });
  var members = S.users.filter(function (u) { return u.plan === "member"; }).length;
  var trials = S.users.filter(function (u) { return u.plan === "trial" && !u.banned; }).length;
  var banned = S.users.filter(function (u) { return u.banned; }).length;
  return '<div class="grid">' + [["Участников", members], ["На пробе", trials], ["Забанено", banned], ["Всего", S.users.length]].map(function (row) {
      return '<div class="card tile"><small class="muted">' + row[0] + '</small><b class="num" data-to="' + row[1] + '">' + row[1] + "</b></div>";
    }).join("") + "</div>" +
    '<div class="card"><h3>Выдать полный доступ</h3><form id="grant-form" class="form"><div class="two">' +
    '<input name="query" required placeholder="@username / ID" aria-label="Пользователь">' +
    '<input name="limit" type="number" min="1" max="5000" placeholder="Лимит/день" aria-label="Лимит лидов в день"></div>' +
    '<button class="btn main" type="submit">' + ic("plus") + "Выдать</button></form>" +
    '<p class="muted small">По @username — если человек уже нажимал /start. Иначе — по ID или создайте ключ.</p></div>' +
    '<div class="card"><h3>Пользователи</h3><input id="user-q" value="' + esc(S.userQuery) + '" placeholder="Поиск по @username или ID" autocomplete="off">' +
    (users.length ? users.map(userRow).join("") : '<p class="muted" style="margin-top:10px">Никого не найдено.</p>') + "</div>" +
    '<div class="card"><h3>Рассылка</h3><form id="broadcast-form"><textarea name="text" maxlength="4000" required rows="4" placeholder="Текст сообщения"></textarea>' +
    '<button class="btn" type="submit" style="width:100%;margin-top:8px">' + ic("send") + "Отправить всем, кроме забаненных</button></form></div>";
}

function adminKeys() {
  return '<div class="card"><h3>Новый ключ доступа</h3><form id="key-create" class="form">' +
    '<label>Для кого (необязательно)<input name="for_user" placeholder="@username или ID" maxlength="64"></label>' +
    '<div class="two"><label>Лимит лидов в день<input name="limit" type="number" min="0" max="5000" value="70"></label>' +
    '<label>Бонус запросов<input name="bonus" type="number" min="0" max="1000" value="0"></label></div>' +
    '<div class="two"><label>Активаций<input name="uses" type="number" min="1" max="1000" value="1"></label>' +
    '<label>Заметка<input name="note" maxlength="120" placeholder="например, оплатил"></label></div>' +
    '<button class="btn main" type="submit">' + ic("key") + "Создать ключ</button></form>" +
    (S.newKey ? '<div class="card" style="margin-bottom:0"><p class="muted small">Ключ создан. Пользователь вводит его в приложении или командой /key.</p><div class="row g"><span class="code">' + esc(S.newKey) +
      '</span><button class="ghost" style="flex:none" data-act="copykey" data-v="' + esc(S.newKey) + '">' + ic("copy") + "Копировать</button></div></div>" : "") +
    "</div>" +
    '<div class="card"><h3>Ключи</h3>' + (S.keys.length ? S.keys.map(function (key) {
      return '<div class="usr"><div class="row"><span class="code">' + esc(key.code) + '</span><button class="chip mini" data-act="delkey" data-v="' + esc(key.code) + '">' + ic("trash") + "</button></div>" +
        '<p class="muted small">' + (key.for_user ? "для " + esc(key.for_user) + " · " : "для любого · ") +
        (key.daily_limit ? "лимит " + key.daily_limit + " · " : "") + (key.bonus ? "+" + key.bonus + " запросов · " : "") +
        "осталось активаций " + key.uses_left + (key.used_by ? " · активировали: " + esc(key.used_by) : "") +
        (key.note ? " · " + esc(key.note) : "") + "</p></div>";
    }).join("") : '<p class="muted">Ключей пока нет.</p>') + "</div>";
}

function adminLeads() {
  return '<div class="card"><form id="aleads-form" class="keyform"><input name="q" value="' + esc(S.adminQuery) +
    '" placeholder="Название, город, телефон или @username"><button class="btn" type="submit">' + ic("search") + "</button></form></div>" +
    (S.adminLeads.length ? S.adminLeads.map(function (lead) {
      return '<div class="card"><div class="row"><b>' + esc(lead.name) + '</b><span class="badge">' + esc(lead.hot) + "</span></div>" +
        '<p class="muted small">' + esc(lead.country) + " · " + esc(lead.city) + (lead.niche ? " · " + esc(lead.niche) : "") +
        " · " + esc(STATUS_NAMES[lead.status] || lead.status) + " · у " + esc(lead.owner) + "</p>" +
        (lead.phone ? '<p class="small">' + esc(lead.phone) + "</p>" : "") +
        (lead.explain ? '<p class="why">' + esc(lead.explain) + "</p>" : "") +
        '<div class="urow"><button data-act="blocklead" data-id="' + lead.id + '">' + ic("ban") + " В чёрный список</button></div></div>";
    }).join("") : '<div class="empty"><p>Лидов не найдено</p></div>');
}

function table(rows, headers) {
  if (!rows || !rows.length) return '<p class="muted">Пока нет данных.</p>';
  return '<div style="overflow-x:auto"><table class="tbl"><tr>' + headers.map(function (h) { return "<th>" + h + "</th>"; }).join("") + "</tr>" +
    rows.map(function (row) {
      return "<tr><td>" + esc(row.name) + "</td><td>" + esc(row.leads) + "</td><td>" + esc(row.clients || 0) + "</td><td>" + esc(row.avg || 0) + "</td></tr>";
    }).join("") + "</table></div>";
}

function adminOverview() {
  var o = S.overview;
  if (!o) return '<div class="dots"><i></i><i></i><i></i></div>';
  return '<div class="grid">' + [["Пользователей", o.users.total], ["Участников", o.users.members], ["Пробу использовали", o.users.trial_used], ["Пробу не начали", o.users.trial_left],
      ["Лидов выдано", o.leads.total], ["Связались", o.leads.contacted], ["Клиентов", o.leads.clients], ["Забанено", o.users.banned]].map(function (row) {
      return '<div class="card tile"><small class="muted">' + row[0] + '</small><b class="num" data-to="' + (row[1] || 0) + '">' + (row[1] || 0) + "</b></div>";
    }).join("") + "</div>" +
    '<div class="card"><h3>По нишам</h3>' + table(o.niches, ["Ниша", "Лиды", "Клиенты", "Приор."]) + "</div>" +
    '<div class="card"><h3>По городам</h3>' + table(o.cities, ["Город", "Лиды", "Клиенты", "Приор."]) + "</div>" +
    '<div class="card"><h3>Внешние сервисы</h3><p class="muted small">Geoapify сегодня: ' + esc(o.api.geoapify_day) +
    " кредитов · нейросеть сегодня: " + esc(o.api.ai_day) + " запросов · Google за месяц: " + esc(o.api.google_month) + "</p></div>";
}

function adminBlocked() {
  return '<div class="card"><h3>Добавить бизнес</h3><form id="block-form" class="keyform"><input name="text" required placeholder="Телефон, сайт, email или @telegram">' +
    '<button class="btn" type="submit">' + ic("ban") + "</button></form>" +
    '<p class="muted small">Такой бизнес больше никому не выдаётся. Лид можно добавить и из вкладки «Все лиды».</p></div>' +
    '<div class="card"><h3>Чёрный список</h3>' + (S.blocked.length ? S.blocked.map(function (item) {
      return '<div class="usr"><div class="row"><b>' + esc(item.label) + '</b><button class="chip mini" data-act="unblock" data-v="' + esc(item.label) + '">Убрать</button></div></div>';
    }).join("") : '<p class="muted">Пусто.</p>') + "</div>";
}

function adminErrors() {
  var errors = S.errors || { recent: [], day: {} };
  var names = { osm: "OpenStreetMap", geoapify: "Geoapify", google: "Google", gemini: "Нейросеть" };
  var day = Object.keys(errors.day || {});
  return '<div class="card"><h3>За сутки</h3>' + (day.length ? day.map(function (key) {
      return '<div class="row"><span>' + esc(names[key] || key) + "</span><b>" + esc(errors.day[key]) + "</b></div>";
    }).join("") : '<p class="muted">Ошибок нет — все источники отвечают.</p>') + "</div>" +
    '<div class="card"><h3>Последние</h3>' + (errors.recent.length ? errors.recent.map(function (item) {
      return '<div class="err"><b>' + esc(names[item.provider] || item.provider) + '</b> <span class="muted small">' +
        esc(new Date(item.created_at * 1000).toLocaleString("ru-RU")) + "</span><p class=\"muted small\">" + esc(item.message) + "</p></div>";
    }).join("") : '<p class="muted">Пусто.</p>') + "</div>" +
    '<p class="muted small">Ошибка одного источника не ломает поиск: остальные продолжают работать.</p>';
}

function vAdmin() {
  if (!S.admin) return '<section class="screen"><div class="card empty">Нет доступа.</div></section>';
  var views = { users: adminUsers, keys: adminKeys, leads: adminLeads, overview: adminOverview, blocked: adminBlocked, errors: adminErrors };
  return '<section class="screen"><h2>Админ-панель</h2><div class="atabs">' + ADMIN_TABS.map(function (item) {
      return '<button class="chip ' + (S.atab === item[0] ? "on" : "") + '" data-act="atab" data-v="' + item[0] + '">' + item[1] + "</button>";
    }).join("") + "</div>" + (views[S.atab] || adminUsers)() + "</section>";
}

/* ---------- Отрисовка ---------- */

function countUp(element, value) {
  var start = performance.now();
  (function frame(now) {
    var progress = Math.min(1, (now - start) / 700);
    element.textContent = Math.round(value * (1 - Math.pow(1 - progress, 3)));
    if (progress < 1) requestAnimationFrame(frame);
  })(start);
}

function render(keepScroll) {
  var oldScroll = window.scrollY;
  var views = {
    "search": S.loading ? loadingView : vSearch,
    "leads": vLeads,
    "scripts": vScripts,
    "stats": vStats,
    "faq": vFaq,
    "admin": vAdmin
  };
  if (S.tab === "admin" && !S.admin) S.tab = "search";
  $("#app").classList.toggle("still", Boolean(keepScroll));
  $("#app").innerHTML = views[S.tab]();
  $("#tabs").innerHTML = TABS.filter(function (tab) {
    return tab[0] !== "admin" || S.admin;
  }).map(function (tab) {
    return '<button class="' + (S.tab === tab[0] ? "on" : "") +
      '" data-act="tab" data-v="' + tab[0] + '">' + ic(tab[2]) + "<span>" + tab[1] + "</span></button>";
  }).join("");
  document.querySelectorAll(".num").forEach(function (element) {
    var value = Number(element.dataset.to) || 0;
    if (keepScroll) element.textContent = String(value);
    else countUp(element, value);
  });
  window.scrollTo(0, keepScroll ? oldScroll : 0);
}

function openSheet(html) {
  var sheet = $("#sheet");
  sheet.innerHTML = '<div class="sheet">' + html + "</div>";
  sheet.classList.add("show");
  document.body.style.overflow = "hidden";
}

function setSheetBody(html) {
  var inner = $("#sheet .sheet");
  if (inner) inner.innerHTML = html;
  else openSheet(html);
}

function closeSheet() {
  var sheet = $("#sheet");
  sheet.classList.remove("show");
  sheet.innerHTML = "";
  document.body.style.overflow = "";
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("#theme").innerHTML = ic(theme === "dark" ? "sun" : "moon");
  var background = theme === "dark" ? "#151619" : "#f3f3f4";
  document.querySelector('meta[name="theme-color"]').content = background;
  try {
    if (tg) {
      tg.setHeaderColor(background);
      tg.setBackgroundColor(background);
    }
  } catch (_) {}
}

function saveLeadStatus(lead, nextStatus) {
  var previous = lead.status;
  lead.status = nextStatus;
  render(true);
  api("/api/leads/" + encodeURIComponent(lead.id) + "/status", {
    method: "POST", body: JSON.stringify({ status: nextStatus })
  }).then(function () {
    return loadStats();
  }).then(function () {
    if (S.tab === "leads") render(true);
    toast("Статус лида обновлён.");
  }).catch(function (error) {
    lead.status = previous;
    render(true);
    toast(error.message);
  });
}

function adminAction(path, body, message) {
  return api(path, { method: "POST", body: JSON.stringify(body) }).then(function (result) {
    return loadAdmin().then(function () {
      render(true);
      toast((result && result.message) || message);
    });
  }).catch(function (error) { toast(error.message); });
}

function findLead(id) {
  return leads.filter(function (item) { return String(item.id) === String(id); })[0];
}

function clickHandler(event) {
  var target = event.target;
  if (target.closest(".hot") == null) {
    document.querySelectorAll(".hot.open").forEach(function (node) { node.classList.remove("open"); });
  }
  if (target.id === "sheet") { closeSheet(); return; }

  if (target.closest("#theme")) {
    hap();
    setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    return;
  }

  var link = target.closest(".ct a,.contact,a[data-ext]");
  if (link && tg) {
    if (/^https?:/.test(link.href)) {
      event.preventDefault();
      openLink(link.href);
    }
    return;
  }

  var button = target.closest("[data-act]");
  if (!button || button.disabled) return;
  hap();
  var action = button.dataset.act;
  var value = button.dataset.v;
  var id = button.dataset.id ? decodeURIComponent(button.dataset.id) : "";

  if (action === "tab") {
    S.tab = value;
    if (S.tab === "admin") {
      render();
      loadAdmin().then(function () { render(true); }).catch(function (error) { S.tab = "search"; render(); toast(error.message); });
    } else if (S.tab === "scripts") {
      if (S.scriptNiche === CUSTOM_NICHE) S.scriptNiche = 0;
      render();
      loadScripts().then(function () { if (S.tab === "scripts") render(true); }).catch(function (error) { toast(error.message); });
    } else {
      render();
    }
  } else if (action === "niche") {
    S.niche = Number(value);
    render(true);
  } else if (action === "flt") {
    S.flt = value;
    render(true);
  } else if (action === "count") {
    S.count = Number(value);
    render(true);
  } else if (action === "filter") {
    S.filter = value;
    render(true);
  } else if (action === "go") {
    go();
  } else if (action === "demand") {
    showDemand();
  } else if (action === "pickniche") {
    S.niche = Number(value);
    closeSheet();
    S.tab = "search";
    render();
    toast("Ниша выбрана: " + nicheTitle(S.niche) + ".");
  } else if (action === "close") {
    closeSheet();
  } else if (action === "offer") {
    showTrialOffer(S.trialOffer || { message: S.access && S.access.trial_message });
  } else if (action === "status") {
    var lead = findLead(id);
    if (lead) saveLeadStatus(lead, lead.status === value ? "new" : value);
  } else if (action === "more") {
    S.open[id] = !S.open[id];
    render(true);
  } else if (action === "leadscript" || action === "leadkind") {
    var scriptLead = findLead(id);
    if (scriptLead) generateLeadScript(scriptLead, action === "leadkind" ? value : "first");
  } else if (action === "copygen") {
    copyText(S.sheetText || "");
  } else if (action === "savegen") {
    saveGenerated(value, button.dataset.n || "");
  } else if (action === "export") {
    api("/api/export", { method: "POST" }).then(function (data) {
      toast(data.message || "Excel-файл придёт в чат с ботом.");
    }).catch(function (error) { toast(error.message); });
  } else if (action === "sniche") {
    S.scriptNiche = Number(value);
    S.scripts = [];
    S.scriptEdit = null;
    render(true);
    loadScripts().then(function () { render(true); }).catch(function (error) { toast(error.message); });
  } else if (action === "sopen") {
    S.scriptOpen[id] = true;
    render(true);
  } else if (action === "scopy") {
    var script = S.scripts.filter(function (item) { return String(item.id) === id; })[0];
    if (script) copyText(script.body);
  } else if (action === "sedit") {
    S.scriptEdit = Number(id);
    render(true);
  } else if (action === "scancel") {
    S.scriptEdit = null;
    render(true);
  } else if (action === "sdel") {
    api("/api/scripts/" + encodeURIComponent(id), { method: "DELETE" }).then(function () {
      return loadScripts();
    }).then(function () { render(true); toast("Скрипт удалён."); }).catch(function (error) { toast(error.message); });
  } else if (action === "genniche") {
    generateNicheScript(value);
  } else if (action === "atab") {
    S.atab = value;
    S.newKey = "";
    render(true);
    loadAdmin().then(function () { render(true); }).catch(function (error) { toast(error.message); });
  } else if (action === "edit") {
    var user = S.users.filter(function (item) { return String(item.id) === id; })[0];
    if (!user) return;
    S.editId = S.editId === user.id ? null : user.id;
    S.editVal = user.lim;
    render(true);
  } else if (action === "limd") {
    S.editVal = Math.max(0, Math.min(5000, S.editVal + Number(value)));
    render(true);
  } else if (action === "limset") {
    S.editVal = Number(value);
    render(true);
  } else if (action === "limcancel") {
    S.editId = null;
    render(true);
  } else if (action === "limsave") {
    var editId = S.editId;
    S.editId = null;
    adminAction("/api/admin/users/" + encodeURIComponent(editId) + "/limit", { limit: S.editVal }, "Лимит обновлён.");
  } else if (action === "access") {
    adminAction("/api/admin/users/" + encodeURIComponent(id) + "/access", { approved: value === "1" },
      value === "1" ? "Полный доступ выдан." : "Полный доступ закрыт.");
  } else if (action === "bonus") {
    adminAction("/api/admin/users/" + encodeURIComponent(id) + "/bonus", { amount: Number(value) }, "Запросы добавлены.");
  } else if (action === "ban") {
    adminAction("/api/admin/users/" + encodeURIComponent(id) + "/ban", { banned: value === "1" },
      value === "1" ? "Пользователь заблокирован." : "Пользователь разблокирован.");
  } else if (action === "copykey") {
    copyText(value);
  } else if (action === "delkey") {
    api("/api/admin/keys/" + encodeURIComponent(value), { method: "DELETE" }).then(function () {
      return loadAdmin();
    }).then(function () { render(true); toast("Ключ удалён."); }).catch(function (error) { toast(error.message); });
  } else if (action === "blocklead") {
    adminAction("/api/admin/blocked", { lead_id: Number(id) }, "Бизнес добавлен в чёрный список.");
  } else if (action === "unblock") {
    adminAction("/api/admin/unblock", { label: value }, "Убрано из чёрного списка.");
  } else if (action === "tip") {
    var wasOpen = button.classList.contains("open");
    document.querySelectorAll(".hot.open").forEach(function (node) { node.classList.remove("open"); });
    if (!wasOpen) button.classList.add("open");
  } else if (action === "refresh") {
    refreshAll().then(function () { toast("Данные обновлены."); }).catch(function (error) { toast(error.message); });
  }
}

document.addEventListener("click", clickHandler);
document.addEventListener("input", function (event) {
  if (event.target.id === "city") S.city = event.target.value;
  if (event.target.id === "cn") S.custom = event.target.value;
  if (event.target.id === "user-q") {
    S.userQuery = event.target.value;
    var position = event.target.selectionStart;
    render(true);
    var input = $("#user-q");
    if (input) { input.focus(); try { input.setSelectionRange(position, position); } catch (_) {} }
  }
});
document.addEventListener("change", function (event) {
  if (event.target.id === "country") {
    S.country = event.target.value;
    render(true);
  }
});
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && $("#sheet").classList.contains("show")) closeSheet();
});

function formValue(form, name) {
  return String(new FormData(form).get(name) || "").trim();
}

document.addEventListener("submit", function (event) {
  var form = event.target;
  var id = form.id;
  if (!id) return;
  event.preventDefault();
  if (id === "key-form") {
    var code = formValue(form, "code").toUpperCase();
    if (code.length < 4) { toast("Введите ключ доступа."); return; }
    api("/api/key", { method: "POST", body: JSON.stringify({ code: code }) }).then(function (result) {
      closeSheet();
      return loadMe().then(function () { render(); toast(result.message || "Ключ активирован."); });
    }).catch(function (error) { toast(error.message); });
  } else if (id === "script-form") {
    var payload = {
      niche: S.scriptNiche, kind: form.dataset.kind || "first",
      title: formValue(form, "title"), body: formValue(form, "body")
    };
    if (!payload.title || !payload.body) { toast("Заполните название и текст."); return; }
    api("/api/scripts/" + encodeURIComponent(form.dataset.id), { method: "PUT", body: JSON.stringify(payload) }).then(function (result) {
      S.scriptEdit = null;
      return loadScripts().then(function () {
        render(true);
        toast(result.copy ? "Сохранено как ваш скрипт." : "Скрипт сохранён.");
      });
    }).catch(function (error) { toast(error.message); });
  } else if (id === "grant-form") {
    var limit = formValue(form, "limit");
    adminAction("/api/admin/grant", { query: formValue(form, "query"), limit: limit ? Number(limit) : null }, "Доступ выдан.");
  } else if (id === "key-create") {
    api("/api/admin/keys", {
      method: "POST",
      body: JSON.stringify({
        for_user: formValue(form, "for_user"), limit: Number(formValue(form, "limit") || 0),
        bonus: Number(formValue(form, "bonus") || 0), uses: Number(formValue(form, "uses") || 1), note: formValue(form, "note")
      })
    }).then(function (result) {
      S.newKey = result.code;
      return loadAdmin().then(function () { render(true); toast("Ключ создан."); });
    }).catch(function (error) { toast(error.message); });
  } else if (id === "aleads-form") {
    S.adminQuery = formValue(form, "q");
    loadAdmin().then(function () { render(true); }).catch(function (error) { toast(error.message); });
  } else if (id === "block-form") {
    adminAction("/api/admin/blocked", { text: formValue(form, "text") }, "Добавлено в чёрный список.");
  } else if (id === "broadcast-form") {
    var text = formValue(form, "text");
    if (!text) { toast("Введите текст рассылки."); return; }
    api("/api/admin/broadcast", { method: "POST", body: JSON.stringify({ text: text }) }).then(function (result) {
      form.reset();
      toast(result.message || "Рассылка запущена.");
    }).catch(function (error) { toast(error.message); });
  }
});

function appReady() {
  if (typeof window.__appReady === "function") window.__appReady();
}

function boot() {
  if (tg) {
    try { tg.ready(); tg.expand(); } catch (_) {}
    if (tg.colorScheme === "light") setTheme("light");
  }
  refreshAll().then(appReady).catch(function (error) {
    appReady();
    var app = $("#app");
    var banned = error.detail && error.detail.code === "banned";
    app.innerHTML = '<section class="screen"><div class="card"><h2>' + (banned ? "Доступ закрыт" : "Не удалось открыть приложение") + "</h2>" +
      '<p class="muted">' + esc(error.message) + '</p><p class="muted small">' +
      (banned ? "" : error.status === 401
        ? "Откройте Mini App через бота в Telegram. Если окно было открыто долго, закройте его и откройте снова."
        : "Проверьте соединение и снова откройте приложение.") +
      "</p>" + (banned ? "" : '<button class="ghost" data-act="refresh">Повторить</button>') + "</div></section>";
    $("#tabs").innerHTML = "";
  });
}

setTheme("dark");
render();
boot();
