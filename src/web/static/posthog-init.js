/**
 * PostHog Analytics & Session Recording Initializer
 *
 * Project Token: phc_Ab8smdwdH5D7Ymwg6VivfPT5FaC2ThyewEaa6fNXPHWZ
 * Project ID: 654868 (US Cloud)
 * Defaults: 2026-05-30
 *
 * Automatically initializes PostHog with Session Recording explicitly enabled.
 * Reads configuration injected into window.__POSTHOG_CONFIG__ by FastAPI,
 * falls back to /api/posthog/config or localStorage.
 *
 * Guarantees that:
 * - Session Recording is actively started (DOM, mouse movements, clicks, scrolls)
 * - Input text is not masked (maskAllInputs: false) so chat queries & prompts are readable in replay
 * - Passwords remain masked for security
 * - Console logs & errors are captured into session replay
 * - Helper window.PostHogHelper is available to inspect recording status or retrieve the replay URL
 */
(function (window, document) {
  "use strict";

  // 1. PostHog official asynchronous loader snippet (latest v1.x)
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog && window.posthog.__loaded)||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}p||((p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",p.onerror=function(){p=null},(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r));var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],Object.defineProperty(u,"toString",{configurable:!0,enumerable:!0,writable:!0,value:function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}}),Object.defineProperty(u.people,"toString",{configurable:!0,enumerable:!0,writable:!0,value:function(){return u.toString(1)+".people (stub)"}}),o="gu mu yu bu ku init Qu Zu Wu Vu Yu el Gu ec zu lc uc cc hc dc vc capture getExtension Ju fu mc calculateEventProperties gc register register_once register_for_session unregister unregister_for_session wc Uu yc getFeatureFlag getFeatureFlagPayload getFeatureFlagResult getAllFeatureFlags isFeatureEnabled reloadFeatureFlags updateFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSurveysLoaded onSessionId getSurveys getActiveMatchingSurveys onActiveMatchingSurveysChanged renderSurvey displaySurvey cancelPendingSurvey canRenderSurvey canRenderSurveyAsync kc identify setPersonProperties unsetPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset Sc shutdown setIdentity clearIdentity get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException addExceptionStep captureLog startExceptionAutocapture stopExceptionAutocapture loadToolbar get_property getSessionProperty bc rc createPersonProfile setInternalOrTestUser Cu xu opt_in_capturing opt_out_capturing $u has_opted_in_capturing has_opted_out_capturing get_explicit_consent_status is_capturing clear_opt_in_out_capturing nc debug il Os getPageViewId captureTraceFeedback captureTraceMetric Nu".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

  // 2. PostHog Helper Utility for inspection, debugging, and replay link retrieval
  window.PostHogHelper = {
    isRecording: function () {
      if (!window.posthog) return false;
      if (typeof window.posthog.sessionRecordingStarted === "function") {
        try {
          return window.posthog.sessionRecordingStarted();
        } catch (e) {
          return false;
        }
      }
      return false;
    },

    getSessionId: function () {
      if (window.posthog && typeof window.posthog.get_session_id === "function") {
        try {
          return window.posthog.get_session_id();
        } catch (e) {
          return null;
        }
      }
      return null;
    },

    getReplayUrl: function () {
      if (window.posthog && typeof window.posthog.get_session_replay_url === "function") {
        try {
          const direct = window.posthog.get_session_replay_url();
          if (direct) return direct;
        } catch (e) {}
      }
      const sessId = window.PostHogHelper.getSessionId();
      const projId = (window.__POSTHOG_CONFIG__ && window.__POSTHOG_CONFIG__.projectId) || "654868";
      if (sessId) {
        return "https://us.posthog.com/project/" + projId + "/replay/" + sessId;
      }
      return null;
    },

    startRecording: function () {
      if (window.posthog && typeof window.posthog.startSessionRecording === "function") {
        window.posthog.startSessionRecording();
        console.log("[PostHog] Session Recording explicitly started.");
        return true;
      }
      return false;
    },

    stopRecording: function () {
      if (window.posthog && typeof window.posthog.stopSessionRecording === "function") {
        window.posthog.stopSessionRecording();
        console.log("[PostHog] Session Recording stopped.");
        return true;
      }
      return false;
    },

    status: function () {
      const isLoaded = Boolean(window.posthog && window.posthog.__loaded);
      return {
        loaded: isLoaded,
        recording: window.PostHogHelper.isRecording(),
        sessionId: window.PostHogHelper.getSessionId(),
        replayUrl: window.PostHogHelper.getReplayUrl(),
        distinctId: window.posthog && typeof window.posthog.get_distinct_id === "function" ? window.posthog.get_distinct_id() : null,
      };
    },

    initManual: function (apiKey, apiHost, enableRecording) {
      bootstrapPostHog({
        apiKey: apiKey || "phc_Ab8smdwdH5D7Ymwg6VivfPT5FaC2ThyewEaa6fNXPHWZ",
        apiHost: apiHost || "https://us.i.posthog.com",
        projectId: "654868",
        enableRecording: enableRecording !== false
      });
    }
  };

  // 3. Core initialization logic
  function bootstrapPostHog(config) {
    if (!config || !config.apiKey || typeof config.apiKey !== "string" || config.apiKey.trim() === "") {
      console.info(
        "%c[PostHog]%c POSTHOG_API_KEY chưa được cấu hình trong .env.",
        "color:#f59e0b;font-weight:bold",
        "color:#94a3b8"
      );
      return;
    }

    const apiKey = config.apiKey.trim();
    const host = (config.apiHost || "https://us.i.posthog.com").trim().replace(/\/+$/, "");
    const shouldRecord = config.enableRecording !== false;

    try {
      window.posthog.init(apiKey, {
        api_host: host,
        defaults: "2026-05-30",
        person_profiles: "identified_only",
        autocapture: true,
        capture_pageview: true,
        capture_pageleave: true,
        // Ensure Session Recording is guaranteed
        disable_session_recording: !shouldRecord,
        session_recording: {
          recordCrossOriginIframes: true,
          // maskAllInputs: false ensures prompts and customer chat messages are visible in replay
          maskAllInputs: false,
          maskInputOptions: {
            password: true // Passwords are kept masked for security
          },
          recordCanvas: false,
          collectFonts: true,
          inlineStylesheet: true
        },
        enable_recording_console_log: true,
        loaded: function (ph) {
          if (shouldRecord) {
            try {
              ph.startSessionRecording();
              const replayUrl = window.PostHogHelper.getReplayUrl();
              console.log(
                "%c[PostHog]%c Session Recording is ACTIVE ⏺ | Distinct ID: %c" + ph.get_distinct_id() + (replayUrl ? " | Replay: " + replayUrl : ""),
                "color:#10b981;font-weight:bold;background:#064e3b;padding:2px 6px;border-radius:4px",
                "color:#e2e8f0",
                "color:#38bdf8;font-weight:bold"
              );
            } catch (err) {
              console.warn("[PostHog] Warning calling startSessionRecording:", err);
            }
          } else {
            console.log("[PostHog] Initialized without Session Recording.");
          }

          // Broadcast custom event so UI components can update badges if needed
          window.dispatchEvent(new CustomEvent("posthog:ready", {
            detail: {
              recording: shouldRecord,
              distinctId: ph.get_distinct_id(),
              replayUrl: window.PostHogHelper.getReplayUrl()
            }
          }));
        }
      });
    } catch (e) {
      console.error("[PostHog] Initialization error:", e);
    }
  }

  // 4. Resolve configuration from multiple available sources:
  // Priority 1: Injected window.__POSTHOG_CONFIG__ from FastAPI backend
  if (window.__POSTHOG_CONFIG__ && window.__POSTHOG_CONFIG__.apiKey) {
    bootstrapPostHog(window.__POSTHOG_CONFIG__);
    return;
  }

  // Priority 2: LocalStorage override (handy for debugging without restarting the backend)
  const localKey = localStorage.getItem("POSTHOG_API_KEY") || localStorage.getItem("posthog_api_key");
  const localHost = localStorage.getItem("POSTHOG_HOST") || localStorage.getItem("posthog_host") || "https://us.i.posthog.com";
  if (localKey) {
    bootstrapPostHog({
      apiKey: localKey,
      apiHost: localHost,
      projectId: "654868",
      enableRecording: true
    });
    return;
  }

  // Priority 3: Fetch configuration from backend API endpoint /api/posthog/config
  fetch("/api/posthog/config")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (cfg) {
      if (cfg && cfg.apiKey) {
        bootstrapPostHog(cfg);
      } else {
        // Fallback default with project token if env wasn't loaded
        bootstrapPostHog({
          apiKey: "phc_Ab8smdwdH5D7Ymwg6VivfPT5FaC2ThyewEaa6fNXPHWZ",
          apiHost: "https://us.i.posthog.com",
          projectId: "654868",
          enableRecording: true
        });
      }
    })
    .catch(function () {
      // Direct fallback
      bootstrapPostHog({
        apiKey: "phc_Ab8smdwdH5D7Ymwg6VivfPT5FaC2ThyewEaa6fNXPHWZ",
        apiHost: "https://us.i.posthog.com",
        projectId: "654868",
        enableRecording: true
      });
    });

})(window, document);
