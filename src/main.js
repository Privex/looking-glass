import Vue from 'vue'
import Vuex from 'vuex'
import VueRouter from 'vue-router'

Vue.config.productionTip = false;
import ASNList from './components/ASNList.vue'
import PrefixList from './components/PrefixList.vue'
import LookingGlass from "./components/LookingGlass";
import App from './App.vue'

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
    {path: '/prefixes/:asn', component: PrefixList, name: 'prefixes'},
];

const LG_ENABLED = ('VUE_APP_SHOW_LG' in process.env) ? is_true(process.env.VUE_APP_SHOW_LG) : true;
const PEERAPP_ENABLED = ('VUE_APP_SHOW_PEERAPP' in process.env) ? is_true(process.env.VUE_APP_SHOW_PEERAPP) : true;

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

const prefix_api = {
    list_asns: async function() {
        return new Promise(resolve => {
            var url = `/api/v1/asn_prefixes/`;
            return fetch(url)
            .then((response) => { 
                if (response.status !== 200) {
                    return console.error('non-200 response');
                }
                return response.json().then((data) => {
                    return resolve(data);
                })
            })
        });
    },
    prefixes: async function(query = {}) {
        return new Promise(resolve => {
            var url = '/api/v1/prefixes/';
            var first_q = true;
            for (var q in query) {
                url += (first_q) ? '?' : '&'
                url += `${q}=${query[q]}`;
                first_q = false;
            }
            return fetch(url)
            .then((response) => { 
                if (response.status !== 200) {
                    return console.error('non-200 response');
                }
                return response.json().then((data) => {
                    return resolve(data);
                })
            })
        });
    }
};

const store = new Vuex.Store({
  state: {
    asns: {},
    prefixes: [],
    lg_enabled: LG_ENABLED,
    peerapp_enabled: PEERAPP_ENABLED
  },
  mutations: {
    replaceASNs (state, asns) {
      state.asns = asns;
    },
    replacePrefixes (state, prefixes) {
      state.prefixes = prefixes;
    },
  },
  actions: {
    loadASNs({ commit }, { }) {
      return prefix_api.list_asns().then(d => {
        commit('replaceASNs', d)
      })
    },
    loadPrefixes({ commit }, { query = {} }) {
      return prefix_api.prefixes(query).then(d => {
        commit('replacePrefixes', d);
      })
    }
  }
});

Object.defineProperty(Vue.prototype, '$prefixapi', { value: prefix_api });

new Vue({
  router,
  store,
  created() {
    this.$store.dispatch('loadASNs', {});
  },
  render: h => h(App),
}).$mount('#app');

Vue.config.devtools = true;
