<template>
    <div class="ui raised segment main-box">
        <h1>Prefixes advertised to us by AS{{ asn }} {{ asn_name }}</h1>

        <div class="ui pointing menu">
            <router-link class="item" :to="{name: 'prefixes', params: {family: 'all', asn: asn, page: current_page}}" exact active-class="active">
                All
            </router-link>
            <router-link class="item" :to="{name: 'prefixes', params: {family: 'v4', asn: asn, page: current_page}}" exact active-class="active">
                IPv4
            </router-link>
            <router-link class="item" :to="{name: 'prefixes', params: {family: 'v6', asn: asn, page: current_page}}" exact active-class="active">
                IPv6
            </router-link>
        </div>

        <table class="ui table compact">
            <thead>
                <tr><th>Prefix</th><th>Next Hop</th><th>IXP</th><th>ASN Path</th></tr>
            </thead>
            <tbody>
                <tr v-for="prefix of prefixes" :key="prefix._id">
                    <td>{{ prefix.prefix }}</td>
                    <td>{{ prefix.first_hop }}</td>
                    <td>{{ prefix.ixp }}</td>
                    <td>{{ trim_path(prefix.asn_path) }}</td>
                </tr>
            </tbody>
        </table>

        pages.all is {{ this.$store.state.pages.all }}
        <br/>
        pages.v4 is {{ this.$store.state.pages.v4 }}
        <br/>
        pages.v6 is {{ this.$store.state.pages.v6 }}
        <br/>
        page_count is {{ page_count }}
        <br/>
        current_page is {{ current_page }}
        <br/>

        <Pager v-if="page_count > 1" v-bind:pageCount="page_count" v-bind:value="current_page" v-on:input="turn_page($event)" />
    </div>
</template>

<script>
import Pager from './Pager.vue'

export default {
    name: 'PrefixList',
    props: [],
    components: {
        Pager
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
        }
    },

    beforeRouteUpdate (to, from, next) {
        this.$store.dispatch('loadPrefixes', {query: {family: to.params.family, asn: to.params.asn, page: to.params.page}});
        next();
    },

    mounted() {
        this.$store.dispatch('loadPrefixes', {query: {family: this.family, asn: this.asn, page: this.page}});
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
        }
    }

}
</script>

