<template>
  <div id="converter-app">
    <div class="ui pointing menu">
      <router-link class="item" to="/" exact active-class="active" v-if="lg_enabled">
        Trace / Ping
      </router-link>
      <router-link class="item" to="/" exact active-class="active" v-if="!lg_enabled">
        BGP Peers and Prefixes
      </router-link>
      <router-link class="item" to="/peers" active-class="active" v-if="lg_enabled && peerapp_enabled">
        BGP Peers and Prefixes
      </router-link>
      <router-link class="item" to="/prefixes/search" active-class="active" v-if="peerapp_enabled">
        Search BGP Prefixes
      </router-link>
    </div>
    <router-view />
  </div>
</template>

<script>

export default {
  name: 'App',
  components: {},
  computed: {
    peerapp_enabled() {
      return this.$store.state.peerapp_enabled
    },
    lg_enabled() {
      return this.$store.state.lg_enabled
    },
    api_error() {
      return this.$store.state.error;
    }
  }
}
</script>


