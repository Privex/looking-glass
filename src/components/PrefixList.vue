<template>
    <div class="ui raised segment main-box">
        <h1>Prefixes advertised to us by AS{{ asn }} {{ asn_name }}</h1>
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
    </div>
</template>

<script>

export default {
    name: 'PrefixList',
    props: [],
    data: function() {
        return {
            
        }
    },

    methods: {
        trim_path(path) {
            if (path.length > 7) {
                return `${path.slice(0,5).join(', ')} ... ${path.slice(-3)}`
            }
            return path.join(', ')
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

