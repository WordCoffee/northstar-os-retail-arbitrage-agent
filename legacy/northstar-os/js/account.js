/* ==========================================================================
   NORTHSTAR OS — ACCOUNT VIEW (subscriber-ready beta surface)
   Active subscriber identity + plan, the live-gate entitlements matrix, the
   beta plan catalog, and an honest beta-status panel. Everything reads the
   labeled demo subscriber fixture (zero network, gates stay off). A plan
   ENTITLES a gate — it never opens one.
   ========================================================================== */
(function () {
  'use strict';
  var NS = window.NS;

  function demoSub() {
    var d = (typeof NS.DEMO === 'function') ? NS.DEMO() : null;
    return (d && d.subscriber) ? d.subscriber : null;
  }

  function renderIdentity() {
    var el = document.getElementById('acct-identity');
    var sub = demoSub();
    if (!el || !sub) return;
    var i = sub.identity || {};
    var s = sub.subscription || {};
    var plan = NS.activePlan();
    el.innerHTML =
      '<div class="acct-id-grid">' +
        '<div class="acct-cell"><span class="lbl">Profile</span><span class="val" data-acct="profile-id">' + NS.escapeHtml(i.profileId || '—') + '</span></div>' +
        '<div class="acct-cell"><span class="lbl">Owner</span><span class="val">' + NS.escapeHtml(i.owner || '—') + '</span></div>' +
        '<div class="acct-cell"><span class="lbl">Principal</span><span class="val">' + NS.escapeHtml(i.principal || '—') + '</span></div>' +
        '<div class="acct-cell"><span class="lbl">Resolver</span><span class="val" data-acct="resolver">' + NS.escapeHtml(i.resolver || '—') + '</span></div>' +
        '<div class="acct-cell"><span class="lbl">Plan</span><span class="val gold" data-acct="plan">' + NS.escapeHtml(plan ? plan.name : '—') + '</span></div>' +
        '<div class="acct-cell"><span class="lbl">Status</span><span class="val good" data-acct="status">' + NS.escapeHtml(s.status || '—') + '</span></div>' +
      '</div>' +
      '<p class="dim" style="margin-top:10px">' + NS.escapeHtml(i.resolverNote || '') + '</p>' +
      '<p class="dim">' + NS.escapeHtml(sub.gateStateNote || '') + '</p>';
  }

  function renderMatrix() {
    var el = document.getElementById('acct-matrix');
    if (!el) return;
    var plan = NS.activePlan();
    var planId = plan ? plan.id : null;
    var planGates = (plan && plan.entitled_gates) || [];
    var rows = Object.keys(NS.gates).map(function (gate) {
      var g = NS.gates[gate];
      var entitled = planId && planGates.indexOf(gate) !== -1;
      var covers = NS.planEntitles(gate).join(', ');
      return '<tr data-gate="' + NS.escapeHtml(gate) + '">' +
        '<td class="mono">' + NS.escapeHtml(gate) + '</td>' +
        '<td>' + NS.escapeHtml(g.label) + '</td>' +
        '<td><span class="st-pill crimson">' + (g && g.off ? 'Authorization required' : 'LIVE authorized') + '</span></td>' +
        '<td>' + (entitled ? '<span class="st-pill steel">Entitled</span>' : '<span class="dim">—</span>') + '</td>' +
        '<td class="mono dim">' + NS.escapeHtml(covers || '—') + '</td>' +
      '</tr>';
    }).join('');
    el.innerHTML =
      '<div class="table-wrap"><table class="svc gate-matrix"><thead><tr>' +
      '<th scope="col">Gate</th><th scope="col">Live action</th><th scope="col">Live status</th>' +
      '<th scope="col">Active plan covers</th><th scope="col">Plans that entitle</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }

  function renderPlans() {
    var el = document.getElementById('acct-plans');
    var sub = demoSub();
    if (!el || !sub) return;
    var plan = NS.activePlan();
    var planId = plan ? plan.id : null;
    var html = (sub.plans || []).map(function (p) {
      var active = p.id === planId;
      var services = (p.services || []).map(function (s) {
        return '<span class="svc-chip">' + NS.escapeHtml(s) + '</span>';
      }).join('');
      var gates = (p.entitled_gates || []).map(function (g) {
        return '<span class="gate-chip" data-gate-chip="' + NS.escapeHtml(g) + '">' + NS.escapeHtml(g) + '</span>';
      }).join('');
      return '<div class="plan-card' + (active ? ' active' : '') + '" data-plan="' + NS.escapeHtml(p.id) + '">' +
        '<div class="plan-head"><h4>' + NS.escapeHtml(p.name) + '</h4>' +
        (active ? '<span class="plan-tag">your plan</span>' : '<span class="hint">tier ' + (p.tier || 1) + '</span>') +
        '</div>' +
        '<div class="plan-price">$' + p.price + '<span class="dim">/mo</span></div>' +
        '<p class="plan-blurb">' + NS.escapeHtml(p.blurb || '') + '</p>' +
        '<div class="plan-services">' + (services || '<span class="dim">—</span>') + '</div>' +
        '<div class="plan-gates">' + (gates || '<span class="dim">no live gates included</span>') + '</div>' +
      '</div>';
    }).join('');
    el.innerHTML = html;
  }

  function renderBetaStatus() {
    var el = document.getElementById('acct-beta-status');
    if (!el) return;
    var names = Object.keys(NS.gates);
    var off = names.filter(function (g) { return NS.gates[g] && NS.gates[g].off; }).length;
    el.innerHTML =
      '<span class="st-pill gold">beta build</span> ' +
      '<span class="dim">' + off + ' / ' + names.length + ' live gates off · demo data · no live calls · execute-only-by-approval</span>';
  }

  function onMount() {
    renderIdentity();
    renderMatrix();
    renderPlans();
    renderBetaStatus();
  }

  var prevOnMount = NS.onMount;
  NS.onMount = function (route) {
    if (route === 'account') onMount();
    if (prevOnMount) prevOnMount(route);
  };
  window.NS.account = {
    renderIdentity: renderIdentity,
    renderMatrix: renderMatrix,
    renderPlans: renderPlans,
    renderBetaStatus: renderBetaStatus,
  };
})();