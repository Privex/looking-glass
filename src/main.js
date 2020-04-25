import Vue from 'vue'
import Vuex from 'vuex'
import VueRouter from 'vue-router'

Vue.config.productionTip = false;
import ASNList from './components/ASNList.vue'
import PrefixList from './components/PrefixList.vue'
import LookingGlass from "./components/LookingGlass";
import App from './App.vue'
import SearchPrefix from "./components/SearchPrefix";

Vue.use(VueRouter);
Vue.use(Vuex);

const is_true = function(val) {
    if (typeof val == "string") {
        return ['1', 'true', 'yes'].indexOf(val.toLowerCase()) !== -1;
    }
    if (typeof val == "number")  return val === 1;
    if (typeof val == "boolean") return val === true;
};

let routes = [];

const peerapp_routes = [
    {path: '/peers', component: ASNList, name: 'peers'},
    {path: '/prefixes/search', component: SearchPrefix, name: 'prefix_search_base'},
    {path: '/prefixes/search/:page', component: SearchPrefix, name: 'prefix_search'},
    {path: '/prefixes/:family/:asn/:page', component: PrefixList, name: 'prefixes'},
];

const LG_ENABLED = ('VUE_APP_SHOW_LG' in process.env) ? is_true(process.env.VUE_APP_SHOW_LG) : true;
const PEERAPP_ENABLED = ('VUE_APP_SHOW_PEERAPP' in process.env) ? is_true(process.env.VUE_APP_SHOW_PEERAPP) : true;
const DEFAULT_API_LIMIT = ('VUE_APP_DEFAULT_API_LIMIT' in process.env) ? process.env.VUE_APP_DEFAULT_API_LIMIT : 1000;

if (PEERAPP_ENABLED && !LG_ENABLED) {
    routes.push({path: '/', component: ASNList, name: 'home'})
} else {
    routes.push({path: '/', component: LookingGlass, name: 'home'})
    if (PEERAPP_ENABLED) {
        routes = routes.concat(peerapp_routes);
    }
}


const router = new VueRouter({
    routes
});

async function handle_fetch_error(response, reject) {
    console.error('non-200 response', response);
    return response.json()
        .then((res) => reject(res))
        .catch((e) => {
            console.error("Error decoding JSON:", e);
            reject({
                error: true,
                error_code: "JSON_ERROR_DECODE_FAILED",
                message: "Unknown error occurred"
            });
        });
}
const prefix_api = {
    list_asns: async function() {
        return new Promise((resolve, reject) => {
            var url = `/api/v1/asn_prefixes/`;
            return fetch(url)
            .then((response) => { 
                if (response.status !== 200) return handle_fetch_error(response, reject);
                return response.json().then((data) => {
                    return resolve(data);
                })
            })
        });
    },
    info: async function () {
        return new Promise((resolve, reject) => {
            var url = `/api/v1/info/`;
            return fetch(url)
                .then((response) => {
                    if (response.status !== 200) return handle_fetch_error(response, reject);

                    return response.json().then((data) => {
                        return resolve(data);
                    })
                })
        });
    },
    get_prefix: async function (prefix, query = {}) {
        return new Promise((resolve, reject) => {
            var url = `/api/v1/prefix/${prefix}/`;
            var first_q = true;
            for (var q in query) {
                if (!query.hasOwnProperty(q)) continue;
                if ( query[q] === null ) continue;

                if (q === 'asn') {
                    var asn = parseInt(query[q]);
                    url += (first_q) ? '?' : '&';
                    url += `asn=${asn}`;
                } else {
                    url += (first_q) ? '?' : '&';
                    url += `${q}=${query[q]}`;
                }
                first_q = false;
            }
            return fetch(url)
                .then((response) => {
                    if (response.status !== 200) return handle_fetch_error(response, reject);

                    return response.json().then((data) => {
                        return resolve(data);
                    })
                })
        });
    },
    prefixes: async function(query = {}) {
        return new Promise((resolve, reject) => {
            var url = '/api/v1/prefixes/';
            var first_q = true;
            for (var q in query) {
                if (q === 'family' && query[q] === 'all') {
                    continue;
                }
                if (q === 'page') {
                    var page = parseInt(query[q]);
                    url += (first_q) ? '?' : '&';
                    url += `skip=${(page-1)*DEFAULT_API_LIMIT}&limit=${DEFAULT_API_LIMIT}`;
                } else {
                    url += (first_q) ? '?' : '&';
                    url += `${q}=${query[q]}`;
                }
                first_q = false;
            }
            return fetch(url)
            .then((response) => {
                if (response.status !== 200) return handle_fetch_error(response, reject);

                return response.json().then((data) => {
                    return resolve(data);
                })
            })
        });
    }
};

function calculatePrefixes(asn_map) {
    let i4 = 0, i6 = 0;

    for (let v in asn_map) {
        if (!asn_map.hasOwnProperty(v)) continue;
        i4 += asn_map[v].v4;
        i6 += asn_map[v].v6;
    }
    return {all: i4 + i6, v4: i4, v6: i6}
}

const store = new Vuex.Store({
  state: {
    asns: {},
    prefixes: [],
    pages: {},
    search_pages: 0,
    info: {},
    error: {error: false},
    messages: [],
    lg_enabled: LG_ENABLED,
    peerapp_enabled: PEERAPP_ENABLED,
    total_prefixes: {
        all: 0,
        v4: 0,
        v6: 0
    },
    selected_prefix: {prefix: null},
    prefix_search_results: []
  },
  mutations: {
    setTotalPrefixes(state, {total, version='all'}) {
        state.total_prefixes[version] = total;
    },
    replaceTotalPrefixes(state, total_prefixes) {
        state.total_prefixes = total_prefixes;
    },
    replaceASNs (state, asns) {
        state.asns = asns;
        state.total_prefixes = calculatePrefixes(state.asns)
    },
    replacePrefixes (state, prefixes) {
      state.prefixes = prefixes.prefixes;
      state.pages = prefixes.pages;
    },
      replaceInfo(state, info) {
          state.info = info;
          state.info['latest_prefix_time'] = new Date(info['latest_prefix_time'])
      },
      setSelectedPrefix(state, prefix) {
          state.selected_prefix = prefix;
      },
      setPrefixSearchResults(state, results) {
        state.prefix_search_results = results;
      },
      setPrefixSearchPages(state, pages) {
          state.search_pages = pages;
      },
      setError(state, error) {
          state.error = error;
      }
  },
  actions: {
      loadASNs({commit}, {}) {
          return prefix_api.list_asns().then(d => {
              commit('replaceASNs', d);
              this.dispatch('recalculatePrefixTotals', {});
              // this.recalculatePrefixTotals({commit}, {});
          })
      },
      loadInfo({commit}, {}) {
          return prefix_api.info().then(d => {
              commit('replaceInfo', d);
          })
      },
      recalculatePrefixTotals({commit}, {}) {
          return commit('replaceTotalPrefixes', calculatePrefixes(this.state.asns));
      },
      loadPrefixes({commit}, {query = {}}) {
          return prefix_api.prefixes(query).then(d => {
              commit('replacePrefixes', d);
          })
      },
      prefixByID({commit}, id) {
          let p = this.state.prefixes.filter((pfx) => pfx.id === id)[0];
          commit('setSelectedPrefix', p);
          return p;
      },
      prefixByCIDR({commit}, prefix) {
          let p = this.state.prefixes.filter((pfx) => pfx.prefix === prefix)[0];
          commit('setSelectedPrefix', p);
          return p;
      },
      searchPrefixes({commit}, {address, exact = false, asn = null}) {
          return prefix_api.get_prefix(address, {exact: exact, asn: asn})
              .then(results => {
                  commit('setPrefixSearchResults', results['result']);
                  commit('setPrefixSearchPages', results['pages']);
              }).catch(reason => commit('setError', reason))
      },
      clearPrefixSearch({commit}, {}) {
          commit('setPrefixSearchResults', []);
          commit('setPrefixSearchPages', 1);
      },
      error({commit}, {message = "An error has occurred", code = "UNKNOWN"}) {
          commit('setError', {error: true, error_code: code, message: message});
      },
      clearError({commit}, {}) {
          commit('setError', {error: false});
      }
  }
});

Object.defineProperty(Vue.prototype, '$prefixapi', { value: prefix_api });

new Vue({
  router,
  store,
  created() {
    this.$store.dispatch('loadASNs', {}).then(
        () => this.$store.dispatch('recalculatePrefixTotals', {})
    );
    this.$store.dispatch('loadInfo', {});
  },
  render: h => h(App),
}).$mount('#app');

Vue.config.devtools = true;
