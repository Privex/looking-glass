<template>
  <div class="ui raised segment main-box">
    <h1>Prefixes advertised to us by AS{{ asn }} {{ asn_name }}</h1>

    <div class="ui segment">
      <p>
        <strong>NOTE:</strong>
        Prefix rows marked in red, with <code>(STALE)</code> next to the prefix, are considered "stale" by the system.
        <br/>
        This means they're more than <strong>{{ info.prefix_timeout_warn }} seconds</strong> older than the latest
        prefix in the system. This could simply be caused by our prefix importer cron running a little slow, or it may
        be a sign that the ASN it belongs to has stopped advertising that prefix.
      </p>
    </div>

    <div class="ui pointing menu">
      <router-link
        class="item"
        :to="{name: 'prefixes', params: {family: 'all', asn: asn, page: current_page_family('all')}}"
        exact
        active-class="active"
      >
        All
      </router-link>
      <router-link
        class="item"
        :to="{name: 'prefixes', params: {family: 'v4', asn: asn, page: current_page_family('v4')}}"
        exact
        active-class="active"
      >
        IPv4
      </router-link>
      <router-link
        class="item"
        :to="{name: 'prefixes', params: {family: 'v6', asn: asn, page: current_page_family('v6')}}"
        exact
        active-class="active"
      >
        IPv6
      </router-link>
    </div>

    <Pager
            v-if="page_count > 1"
            :page-count="page_count"
            :value="current_page"
            @input="turn_page($event)"
    />

    <table class="ui table compact">
      <thead>
        <tr><th>Prefix</th><th>Next Hop</th><th>IXP</th><th>ASN Path</th></tr>
      </thead>
      <tbody>
        <tr
          v-for="p of prefixes"
          :key="p._id"
          :class="(p.stale) ? 'error' : ''"
        >
          <td>
            <span class="link" @click="prefix_modal(p)">{{ p.prefix }}</span>
            <span v-if="p.stale"> (STALE)</span>
          </td>
          <td>{{ p.first_hop }}</td>
          <td>{{ p.ixp }}</td>
          <td>{{ trim_path(p.asn_path) }}</td>
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
      <i class="close icon"></i>
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

export default {
    name: 'PrefixList',
    components: {
        Pager, PrefixView
    },
    props: [],

    data: function () {
        return {
            prefix: {'prefix': null}
        }
    },

    computed: {
        prefixes() { return this.$store.state.prefixes },
        asn() { return this.$route.params.asn },
        family() { return this.$route.params.family },
        page() { return this.$route.params.page },
        page_count() { return this.$store.state.pages[this.$route.params.family] },
        current_page() { return this.$route.params.page <= this.$store.state.pages[this.$route.params.family] ? this.$route.params.page : this.$store.state.pages[this.$route.params.family] },
        asn_list() { return this.$store.state.asns },
        asn_name() {
            var a = Number(this.asn);
            if(a in this.asn_list) {
                return this.asn_list[Number(this.asn)].as_name;
            }
            return "";
        },
        info() {
          return this.$store.state.info;
        },
    },

    mounted() {
        this.$store.dispatch('loadPrefixes', {query: {family: this.family, asn: this.asn, page: this.page}});
    },

    methods: {
        trim_path(path) {
            if (path.length > 7) {
                return `${path.slice(0,5).join(', ')} ... ${path.slice(-3)}`
            }
            return path.join(', ')
        },

        turn_page: function(to) {
            this.$router.push({name: 'prefixes', params: {family: this.family, asn: this.asn, page: to}});
        },

        current_page_family: function(fam) {
            return this.$route.params.page <= this.$store.state.pages[fam] ? this.$route.params.page : this.$store.state.pages[fam];
        },
        prefix_modal(m) {
            this.prefix = m;
            $('#prefix-modal').modal('show');
        }
    },

    beforeRouteUpdate (to, from, next) {
        this.$store.dispatch('loadPrefixes', {query: {family: to.params.family, asn: to.params.asn, page: to.params.page}});
        next();
    }

}
</script>

