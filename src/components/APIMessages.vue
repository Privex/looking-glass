<template>
    <div class="error-list">
        <div class="ui message error" v-if="api_error.error">
            <strong>ERROR:</strong> {{ api_error.message }}
        </div>
        <div class="ui message success" v-for="msg in api_messages">
            {{ msg }}
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
