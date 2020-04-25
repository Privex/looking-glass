<template>
  <div class="ui raised segment main-box">
    <div class="ui grid">
      <div class="four wide column">
        <strong>Total Prefixes:</strong> {{ total_prefixes.all }}
      </div>
      <div class="four wide column">
        <strong>Total IPv4 Prefixes:</strong> {{ total_prefixes.v4 }}
      </div>
      <div class="four wide column">
        <strong>Total IPv6 Prefixes:</strong> {{ total_prefixes.v6 }}
      </div>
    </div>
    <table class="ui table compact">
      <thead>
        <tr><th>ASN</th><th>Name</th><th>IPv4 Prefixes</th><th>IPv6 Prefixes</th></tr>
      </thead>
      <tbody>
        <tr
          v-for="asn of sorted_asns"
          :key="asn._id"
        >
          <td>{{ asn.asn }}</td>
          <td
            class="link"
            :data-asn="asn.asn"
            @click="select_asn(asn.asn)"
          >
            {{ asn.as_name }}
          </td>
          <td>{{ asn.v4 }}</td>
          <td>{{ asn.v6 }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>



export default {
    name: 'ASNList',
    props: [],
    data: function() {
        return {
            sort_key: 'v4'
        }
    },

    computed: {

        asns() { return this.$store.state.asns },
        sorted_asns() {
            var sorted = Object.values(this.asns);
            sorted.sort(this.compare_asn).reverse();
            return sorted;
        },
        total_prefixes() {
            return this.$store.state.total_prefixes;
        },
    },

    methods: {
        compare_asn(a, b) {
            let comparison = 0, sk = this.sort_key;
            
            if(a[sk] > b[sk]) { comparison = 1 } 
            else if (a[sk] < b[sk]) { comparison = -1 }

            return comparison
        },
        select_asn(asn) {
            this.$router.push({name: 'prefixes', params: {family: 'all', asn: asn, page: 1}})
        },

    }

}
</script>

