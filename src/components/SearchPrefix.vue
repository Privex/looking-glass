<template>
  <div class="ui raised segment main-box">
    <h1>BGP Prefix Search</h1>

    <APIMessages />

    <p>
      This page allows you to search our looking glass BGP prefix database for IPv4 and IPv6 prefixes,
      as well as individual IP addresses.
    </p>
    <p>
      If you enter a prefix, such as <code>185.130.44.0/16</code> - it will search for that prefix, AND
      any sub-prefixes within that subnet such as <code>185.130.45.0/24</code>
    </p>
    <p>
      If you enter an IP address, such as <code>185.130.44.1</code> - it will search for prefixes which contain
      that IP address, e.g. <code>185.130.44.0/24</code>
    </p>
    <p>Here are some examples for you to try:</p>

    <div class="ui grid">
      <div class="column five wide">
        <p><strong>Example Prefixes:</strong></p>
        <ul>
          <li><code>185.130.0.0/16</code></li>
          <li><code>185.130.44.0/22</code> (Privex EU range)</li>
          <li><code>2a07:e00::/29</code> (Privex EU IPv6)</li>
          <li><code>1.0.0.0/8</code> (all IPs starting with <code>1.</code>)</li>
        </ul>
      </div>
      <div class="column five wide">
        <p><strong>Example IPs:</strong></p>
        <ul>
          <li><code>185.130.44.60</code></li>
          <li><code>2a07:e00::abc</code></li>
        </ul>
      </div>
      <div class="column five wide">
        <p><strong>Example AS numbers:</strong></p>
        <ul>
          <li><code>210083</code> (Privex)</li>
          <li><code>6939</code> (Hurricane Electric)</li>
          <li><code>13335</code> (Cloudflare)</li>
          <li><code>31027</code> (NIANET Denmark)</li>
        </ul>
      </div>
    </div>
    <div class="ui form">
      <div class="ui grid">
        <div class="column ten wide">
          <label for="search_prefix">
            IPv4/IPv6 address or CIDR prefix
          </label>
          <input
            id="search_prefix"
            v-model="search_prefix"
            type="text"
          >
        </div>
        <div class="column six wide">
          <label for="search_prefix">
            (Optional) AS number
          </label>
          <input
            id="search_asn"
            v-model="search_asn"
            type="text"
          >
        </div>
      </div>
    </div>
    <div class="ui divider"></div>
    <Pager
            v-if="page_count > 1"
            :page-count="page_count"
            :value="current_page"
            @input="turn_page($event)"
    />
    <table class="ui table compact">
      <thead>
        <tr>
          <th>Prefix</th>
          <th>Next Hop</th>
          <th>IXP</th>
          <th>ASN</th>
          <th>ASN Path</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td colspan="5">
            <div class="ui active centered inline text loader dimmed">
              Searching...
            </div>
          </td>
        </tr>
        <tr v-if="search_results.length === 0 && has_search && !loading">
          <td
            colspan="5"
            class="text-center"
          >
            <strong>
              No results found.<br><br>
              Either we don't have that IP / prefix in our routing tables, or you've entered an invalid
              IP / prefix.<br><br>
              Ensure your IP / Prefix is formatted corrected.

            </strong>
          </td>
        </tr>
        <tr v-if="!has_search && !loading">
          <td
            colspan="5"
            class="text-center"
          >
            <p>
              To begin, enter an IP address or prefix in the search box.<br><br>
              If you enter an IP address (e.g. 185.130.44.1), we'll search for any prefix containing that IP
              address.<br><br>
              If you enter a prefix (e.g. 185.130.44.0/22), we'll search for that specific prefix,
              AND any sub-prefixes within that prefix (e.g. 185.130.45.0/24)<br><br>
            </p>
          </td>
        </tr>
        <tr
          v-for="p of search_results"
          :key="p._id"
        >
          <td
            class="link"
            @click="prefix_modal(p)"
          >
            {{ p.prefix }}
          </td>
          <td>{{ p.first_hop }}</td>
          <td>{{ p.ixp }}</td>
          <td>{{ p.source_asn }} ( {{ trim_name(p.as_name) }} )</td>
          <td>{{ trim_path(p.asn_path, 2, 2) }}</td>
        </tr>
      </tbody>
    </table>

    <Pager
      v-if="page_count > 1"
      :page-count="page_count"
      :value="current_page"
      @input="turn_page($event)"
    />

    <div
      id="prefix-modal"
      class="ui modal"
    >
      <i class="close icon" />
      <div
        v-if="prefix.prefix"
        class="header"
      >
        Prefix {{ prefix.prefix }}
      </div>
      <PrefixView :prefix="prefix" />
    </div>
  </div>
</template>

<script>
    import Pager from './Pager.vue'
    import PrefixView from './PrefixView.vue'
    import {trim_path, trim_name} from '../helpers'
    import { debounce } from 'underscore'
    import APIMessages from "./APIMessages";

    export default {
        name: 'SearchPrefix',
        components: {
            Pager, PrefixView, APIMessages
        },
        props: [],

        data: function () {
            return {
                prefix: {'prefix': null},
                search_prefix: null,
                search_asn: null,
                loading: false,
            }
        },

        computed: {
            search_results() {
                return this.$store.state.prefix_search_results;
            },
            has_search() {
                return (this.search_prefix !== null && this.search_prefix !== "")
            },
            has_error() {
                return this.$store.state.error.error;
            },
            prefixes() {
                return this.$store.state.prefixes
            },
            asn() {
                return this.$route.params.asn
            },
            family() {
                return this.$route.params.family
            },
            page() {
                return this.$route.params.page
            },
            page_count() {
                return this.$store.state.search_pages
            },
            current_page() {
                return this.$route.params.page <= this.$store.state.search_pages ?
                    this.$route.params.page : this.$store.state.search_pages
            },
            asn_list() {
                return this.$store.state.asns
            },
            asn_name() {
                var a = Number(this.asn);
                if (a in this.asn_list) {
                    return this.asn_list[Number(this.asn)].as_name;
                }
                return "";
            }
        },

        watch: {
            search_prefix(val) {
                if (this.current_page !== 1 && this.current_page !== 0) {
                    this.$router.push({name: 'prefix_search', params: {page: '1'}})
                } else {
                    this.run_search()
                }
                // this.run_search()
            },
            search_asn(val) {
                if (this.current_page !== 1 && this.current_page !== 0) {
                    this.$router.push({name: 'prefix_search', params: {page: '1'}})
                } else {
                    this.run_search()
                }
            },

        },

        mounted() {
            // this.$store.dispatch('loadPrefixes', {query: {family: this.family, asn: this.asn, page: this.page}});
            this.debounce_search = debounce(this.searchPrefixes, 2000);
        },
        methods: {
            trim_path: trim_path,
            trim_name: trim_name,
            run_search () {
                if (this.has_error) this.$store.dispatch('clearError', {});
                if (this.search_results.length > 0) this.$store.dispatch('clearPrefixSearch', {});
                this.loading = true;
                this.debounce_search()
            },
            turn_page (to) {
                this.$router.push({
                    name: 'prefix_search',
                    params: {page: to}
                });
            },

            prefix_modal(m) {
                this.prefix = m;
                $('#prefix-modal').modal('show');
            },
            searchPrefixes() {
                // this.$store.dispatch('clearPrefixSearch', {});
                if ( this.search_prefix !== null && this.search_prefix !== "" ) {
                    this._searchPrefixes(this.search_prefix, false, this.search_asn);
                } else {
                    this.loading = false;
                    // this.$store.dispatch('clearPrefixSearch', {})
                }
            },
            _searchPrefixes(address, exact=false, asn=null, page=null) {
                this.loading = true;
                page = ( page === null ) ? this.page : page;
                this.$store.dispatch('searchPrefixes', {address, exact, asn, page: page})
                    .then((res) => {
                        this.loading = false;
                    }).catch((res) => {
                        this.loading = false;
                    });

            }
        },

        beforeRouteUpdate(to, from, next) {
            if (this.has_error) this.$store.dispatch('clearError', {});
            if (this.search_results.length > 0) this.$store.dispatch('clearPrefixSearch', {});
            this._searchPrefixes(this.search_prefix, false, this.search_asn, to.params.page);
            next();
        }

    }
</script>

