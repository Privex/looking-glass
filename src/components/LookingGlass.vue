
<template>
  <div class="ui row">
    <div class="ui segment raised mainbox">
      <div
        v-if="error"
        class="ui message error"
      >
        {{ error }}
      </div>
      <div
        v-if="message"
        class="ui message success"
      >
        {{ message }}
      </div>
      <div
        id="lg_form"
        class="ui form"
      >
        <label for="host_input">Hostname or IP address (IPv4 / IPv6)</label>
        <input
          id="host_input"
          v-model="host"
          type="text"
          placeholder="8.8.8.8"
          name="host"
        >

        <label for="action_input">Action</label>
        <select
          id="action_input"
          v-model="action"
          name="action"
          class="ui fluid dropdown"
        >
          <option value="trace">
            Traceroute (mtr)
          </option>
          <option value="ping">
            Ping
          </option>
        </select>
        <label for="proto_input">Protocol</label>
        <select
          id="proto_input"
          v-model="proto"
          name="proto"
          class="ui fluid dropdown"
        >
          <option value="any">
            Automatic
          </option>
          <option value="ipv4">
            IPv4
          </option>
          <option value="ipv6">
            IPv6
          </option>
        </select>
        <div class="ui divider" />
        <button
          class="ui button primary fluid"
          @click="send_form"
        >
          Go!
        </button>
      </div>
    </div>
    <div class="ui segment raised mainbox">
      <h3>Results:</h3>
      <p>After you make a request, the results will show up below this text within a few seconds.</p>
      <div
        id="results_segment"
        class="ui fluid segment"
      >
        <div
          v-if="status_data.status === 'waiting'"
          class="ui active dimmer"
        >
          <div class="ui text huge loader">
            Loading
          </div>
        </div>
        <pre id="results_box">{{ result }}</pre>
      </div>
    </div>
  </div>
</template>
<script>
    export default {
        data() {
            return {
                proto: 'any',
                action: 'trace',
                host: '',
                error: null,
                message: null,
                status_data: {
                    status: null,
                    result: null
                }
            }
        },
        computed: {
            result: function () {
                let sd = this.status_data;

                if (sd.result === null || sd.status === null) return 'No request made yet...';
                if (sd.status === 'waiting') return 'Please wait while we process your request...';
                if (sd.status === 'finished') {
                    // clearInterval(window.wait_timer);
                    // this.error = this.message = null;
                    return sd.result;
                }
                return 'Something went wrong processing your request...'
            }
        },
      watch: {
        status_data(val) {
          if (val.status === 'finished') {
            clearInterval(window.wait_timer);
            this.error = this.message = null;
          }
        }
      },
        methods: {
            wait_data: function (req_id) {
                this.load_status(req_id);
                window.wait_timer = setInterval(
                    () => {
                        this.load_status(req_id);
                    }, 2000
                );
            },
            load_status(req_id) {
                $.get(`/api/v1/status/${req_id}`)
                    .then((data) => {
                        this.$set(this, 'status_data', data.result);
                        if (data.result.status === 'finished') {
                            clearInterval(window.wait_timer);
                        }
                    })
                    .catch((err) => {
                        clearInterval(window.wait_timer);
                        this.error = err.responseJSON.message;
                    });
            },
            send_form: function () {
                this.error = this.message = null;
                let url = '/api/v1';
                if (this.action === 'trace') {
                    this.message = `Now running a trace to ${this.host}. The results will appear at the bottom shortly.`;
                    url += '/trace';
                    if (this.proto !== 'any') {
                        url += '/' + this.proto;
                    }
                }
                if (this.action === 'ping') {
                    this.message = `Now pinging ${this.host}. The results will appear at the bottom shortly.`;
                    url += '/ping';
                    if (this.proto !== 'any') {
                        url += '/' + this.proto;
                    }
                }
                $.post(url, {host: this.host})
                    .then((data) => {
                        console.log(data);
                        this.wait_data(data.result.req_id);
                    })
                    .catch((err) => {
                        this.error = err.responseJSON.message;
                        this.message = null;
                    });
            }
        }
    }
</script>
