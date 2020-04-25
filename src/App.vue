<template>
  <div id="converter-app">
    <div class="ui pointing menu">
      <router-link
        v-if="lg_enabled"
        class="item"
        to="/"
        exact
        active-class="active"
      >
        Trace / Ping
      </router-link>
      <router-link
        v-if="!lg_enabled"
        class="item"
        to="/"
        exact
        active-class="active"
      >
        BGP Peers and Prefixes
      </router-link>
      <router-link
        v-if="lg_enabled && peerapp_enabled"
        class="item"
        to="/peers"
        active-class="active"
      >
        BGP Peers and Prefixes
      </router-link>
      <router-link
        v-if="peerapp_enabled"
        class="item"
        to="/prefixes/search/1"
        active-class="active"
      >
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


