console.log('test input all parameters on load')

// console.log(data);

function load_dropdown(s, bburl, valuefunc) {
  //console.log('load_dropdown:')
  //console.log(s)
  $(s).empty()
  $(s).append('<option value="Loading..." selected="selected">Loading...</option>')

  $.ajax(bburl, {
    'success': function(data, textStatus, oo) {
      $(s).empty()
      data['values'].forEach(function(a) {
        //console.log(valuefunc(a));
        $(s).append('<option value="'+valuefunc(a)+'">'+valuefunc(a)+'</option>')
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

// [ [input name 1, url for dropdown 1], [input name 2, url for dropdown 2], ... ]
[
  ['TestVersion', 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches'], 
  ['AnotherInput', 'https://api.bitbucket.org/2.0/repositories/Niam/libdodo/refs/branches']
].forEach(function(title_url) {
  title = title_url[0]
  Array.from($('td[title="'+title+'"] + td .qs-editable-input-disabled')).forEach(function(s) {
    //console.log($(s))

    if($(s).prop('tagName') != 'SELECT') {
      name = $(s).attr('name')
      den = $(s).attr('data-editor-name')
      dti = $(s).attr('data-test-id')
      dic = $(s).attr('data-input-control')
      //console.log(name)
      //console.log(den)
      //console.log(dti)
      //console.log(dic)
      
      id = 'x' + Math.floor(Math.random()*1000000000)
      $(s).replaceWith('<select id="' + id + '" autocomplete="off" class="qs-editable-input-disabled valid" name="'+name+'" data-test-id="'+dti+'" data-editor-name="'+den+'" data-input-control="'+dic+'" ></select>')
      s = '#' + id
    }
    bburl = title_url[1]
    load_dropdown(s, bburl, function(a) {
      return a.name
    })
  })    
})

// todo: locate arguments by test name
id = 'ExecutionBatches_0__Tests_1__Parameter'
s = '#ExecutionBatches_0__Tests_1__Parameter'
name = 'ExecutionBatches[0].Tests[1].Parameter'
if($(s).prop('tagName')!='SELECT') {
  $(s).replaceWith('<select data-test-id="CustomTestParameter" id="' + id + '" name="' + name + '"></select>')
}

bburl = 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches'
load_dropdown(s, bburl, function(a) {
    return '/c echo ' + a.name
})

return data;
