<template>
  <div class="ui buttons">
    <button
      class="ui labeled icon button"
      :class="{disabled: !has_prev}"
      @click="$emit('input', 1);"
    >
      <i class="angle double left icon" />
      First
    </button>
    <button
      class="ui labeled icon button"
      :class="{disabled: !has_prev}"
      @click="$emit('input', parseInt(page) - 1);"
    >
      <i class="angle left icon" />
      Previous
    </button>
    <button class="ui button disabled">
      <i class="page icon" />
      <strong>Page {{ page }} of {{ pageCount }}</strong>
    </button>
    <button
      class="ui right labeled icon button"
      :class="{disabled: !has_next}"
      @click="$emit('input', parseInt(page) + 1);"
    >
      Next
      <i class="angle right icon" />
    </button>
    <button
      class="ui right labeled icon button"
      :class="{disabled: !has_next}"
      @click="$emit('input', last_page);"
    >
      Last
      <i class="angle double right icon" />
    </button>
  </div>
</template>
<script>
export default {
    name: 'Pager',
    props: {
        value: {
            default: 1,
            type: Number
        },
        pageCount: {
            default: 1,
            type: Number
        }
    },
    computed: {
        page() {
            return this.value;
        },
        last_page() {
            return this.pageCount;
        },
        has_next() {
            return this.page < this.pageCount;
        },
        has_prev() {
            return this.page > 1;
        }
    }
}
</script>
