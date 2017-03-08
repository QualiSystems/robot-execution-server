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

// [ [input name 1, url for dropdown 1, dropdown value extraction function 1],
//   [input name 2, url for dropdown 2, dropdown value extraction function 2], ... ]
[
  ['TestVersion', 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches', function(a) {return a.name;}],
  ['AnotherInput', 'https://api.bitbucket.org/2.0/repositories/Niam/libdodo/refs/branches', function(a) {return a.name;}]
].forEach(function(title_url_f) {
  title = title_url_f[0]
  bburl = title_url_f[1]
  f = title_url_f[2]
  Array.from($('td[title="'+title+'"] + td input.qs-editable-input-disabled')).forEach(function(s) {
    name = $(s).attr('name')
    den = $(s).attr('data-editor-name')
    dti = $(s).attr('data-test-id')
    dic = $(s).attr('data-input-control')
    $(s).replaceWith('<select autocomplete="off" class="qs-editable-input-disabled valid" name="'+name+'" data-test-id="'+dti+'" data-editor-name="'+den+'" data-input-control="'+dic+'" ></select>')
  });
  Array.from($('td[title="'+title+'"] + td select.qs-editable-input-disabled')).forEach(function(s) {
    load_dropdown(s, bburl, f)
  });
});

// [ [test name 1, url for dropdown 1, dropdown value extraction function 1],
//   [test name 2, url for dropdown 2, dropdown value extraction function 2], ... ]

[
  ['ping', 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches', function(a) {return a.name;}],
  ['cmd /c', 'https://api.bitbucket.org/2.0/repositories/Niam/libdodo/refs/branches', function(a) {return a.name;}]
].forEach(function(title_url_f) {
    title = title_url_f[0]
    bburl = title_url_f[1]
    f = title_url_f[2]
    e = $('div:has([value="' + title + '"]) + div input[data-test-id="CustomTestParameter"]')
    id = e.attr('id')
    name = e.attr('name')
    e.replaceWith('<select data-test-id="CustomTestParameter" id="'+id+'" name="'+name+'"></select>')
    load_dropdown('div:has([value="' + title + '"]) + div select[data-test-id="CustomTestParameter"]', bburl, f)
});


return data;