<template>
  <div class="ui grid container">
    <div
      v-if="prefix.prefix"
      class="column fourteen wide padded-center"
    >
      <h3>Prefix Information</h3>
      <table
        id="prefix-data"
        class="ui definition table"
      >
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

        computed: {
            prefixes() {
                return this.$store.state.prefixes
            },
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
        }

    }
</script>

