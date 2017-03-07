console.log('test input all parameters on load')

console.log(data);

function load_dropdown(s, bburl) {
  $(s).empty()
  $(s).append('<option value="Loading..." selected="selected">Loading...</option>')

  $.ajax(bburl, {
    'success': function(data, textStatus, oo) {
      $(s).empty()
      data['values'].forEach(function(a) {
        console.log(a.name);
        $(s).append('<option value="'+a.name+'">'+a.name+'</option>')
      })
    },
    'error': function(oo, textStatus, errorThrown) {
      $(s).empty()
      e = textStatus+': ' + errorThrown
      e = e.replace('\n', ' ').replace('\r', ' ')
      $(s).append('<option value="'+e+'">'+e+'</option>')
    }
  })
}


['#topology-inputs-mandatory .qs-editable-input-disabled', '#topologyInputsComponentWrapper .qs-editable-input-disabled'].forEach(function(s) {
  if($(s)) {
    if($(s).prop('tagName') != 'SELECT') {
      name = $(s).prop('name')
      den = $(s).prop('data-editor-name')
      dti = $(s).prop('data-test-id')
      dic = $(s).prop('data-input-control')
      $(s).replaceWith('<select autocomplete="off" class="qs-editable-input-disabled valid" name="'+name+'" data-test-id="'+dti+'" data-editor-name="'+den+' data-input-control="'+dic+'" ></select>')
    }
    bburl = 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches'
    load_dropdown(s, bburl)

  }
});

id = 'ExecutionBatches_0__Tests_1__Parameter'
s = '#ExecutionBatches_0__Tests_1__Parameter'
name = 'ExecutionBatches[0].Tests[1].Parameter'
if($(s).prop('tagName')!='SELECT') {
  $(s).replaceWith('<select data-test-id="CustomTestParameter" id="' + id + '" name="' + name + '"></select>')
}

bburl = 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches'
load_dropdown(s, bburl)



return data;
