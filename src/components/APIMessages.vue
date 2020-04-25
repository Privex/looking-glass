<template>
  <div class="error-list">
    <div
      v-if="api_error.error"
      class="ui message error"
    >
      <strong>ERROR:</strong> {{ api_error.message }}
    </div>
    <div
      v-for="msg in api_messages"
      :key="msg"
      class="ui message success"
    >
      {{ api_messages[msg] }}
    </div>
  </div>
</template>
<script>
    export default {
        name: 'APIMessages',
        props: [],
        computed: {
            api_error() {
                return this.$store.state.error;
            },
            api_messages() {
                return this.$store.state.messages;
            }
        }
    }
</script>
