<template>
    <div class="ui grid container">
<!--        <i class="close icon"></i>-->
        <div class="column fourteen wide padded-center" v-if="prefix.prefix">
            <h3>Prefix Information</h3>
            <table class="ui definition table" id="prefix-data">
                <tbody>
                <tr>
                    <td>Age</td>
                    <td>{{ prefix.age }}</td>
                </tr>
                <tr>
                    <td>ASN and AS Name</td>
                    <td>{{ prefix.source_asn }} - {{ prefix.as_name }}</td>
                </tr>

                <tr>
                    <td>ASN Path</td>
                    <td>{{ prefix.asn_path }}</td>
                </tr>

                <tr>
                    <td>Communities:</td>
                    <td>{{ prefix.communities }}</td>
                </tr>
                <tr>
                    <td>Address Family:</td>
                    <td>{{ prefix.family }}</td>
                </tr>
                <tr>
                    <td>First Hop:</td>
                    <td>{{ prefix.first_hop }}</td>
                </tr>
                <tr>
                    <td>Next Hops:</td>
                    <td>{{ prefix.next_hops }}</td>
                </tr>
                <tr>
                    <td>Internet Exchange (IXP):</td>
                    <td>{{ prefix.ixp }}</td>
                </tr>
                <tr>
                    <td>Last Seen At:</td>
                    <td>{{ prefix.last_seen }}</td>
                </tr>
                <tr>
                    <td>Neighbour:</td>
                    <td>{{ prefix.neighbor }}</td>
                </tr>
                </tbody>
            </table>


        </div>
    </div>


</template>

<script>
    // import Pager from './Pager.vue'

    export default {
        name: 'PrefixView',
        props: {
            prefix: {
                default: () => { return {prefix: null} },
                type: Object
            },
        },

        data: function () {
            return {}
        },

        methods: {
            trim_path(path) {
                if (path.length > 7) {
                    return `${path.slice(0, 5).join(', ')} ... ${path.slice(-3)}`
                }
                return path.join(', ')
            },

            prefix_modal(m) {
                this.prefix = m;
                $('#prefix-modal').modal('show');
            }
        },

        // beforeRouteUpdate(to, from, next) {
        //     this.$store.dispatch('loadPrefixes', {
        //         query: {
        //             family: to.params.family,
        //             asn: to.params.asn,
        //             page: to.params.page
        //         }
        //     });
        //     next();
        // },

        // mounted() {
        //     this.$store.dispatch('loadPrefixes', {query: {family: this.family, asn: this.asn, page: this.page}});
        // },

        computed: {
            prefixes() {
                return this.$store.state.prefixes
            },
            // asn() {
            //     return this.$route.params.asn
            // },
            // family() {
            //     return this.$route.params.family
            // },
            // page() {
            //     return this.$route.params.page
            // },
            // page_count() {
            //     return this.$store.state.pages[this.$route.params.family]
            // },
            // current_page() {
            //     return this.$route.params.page <= this.$store.state.pages[this.$route.params.family] ? this.$route.params.page : this.$store.state.pages[this.$route.params.family]
            // },
            // asn_list() {
            //     return this.$store.state.asns
            // },
            // asn_name() {
            //     var a = Number(this.asn);
            //     if (a in this.asn_list) {
            //         return this.asn_list[Number(this.asn)].as_name;
            //     }
            //     return "";
            // }
        }

    }
</script>

