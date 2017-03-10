console.log('test input all parameters on load')


title2loader = {
  'TestVersion': function(callbacks) {
    var rv = [];
    $.ajax('https://api.github.com/repos/ericrqs/robot-execution-server/tags', {
        'success': function(data, textStatus, oo) {
            data.forEach(function(a) {
                rv.push('tags/'+a.name);
            });
            $.ajax('https://api.github.com/repos/ericrqs/robot-execution-server/branches', {
                'success': function(data2, textStatus2, oo2) {
                    data2.forEach(function(a3) {
                        rv.push(a3.name);
                    })
                    callbacks.forEach(function(a4) {
                        a4(rv);
                    })
                },
                'error': function(oo6, textStatus6, errorThrown6) {
                    var e2 = textStatus6+': ' + errorThrown6;
                    e2 = e2.replace('\n', ' ').replace('\r', ' ');
                    rv.push(e2);
                    callbacks.forEach(function(a5) {
                        a5(rv);
                    });
                }
            });
        },
        'error': function(oo, textStatus, errorThrown) {
            var e = textStatus+': ' + errorThrown;
            e = e.replace('\n', ' ').replace('\r', ' ');
            rv.push(e);
            callbacks.forEach(function(a9) {
                a9(rv);
            });
        }
    });
  },
  'AnotherInput': function(callbacks) {
    var rv=[];
    $.ajax('https://api.bitbucket.org/2.0/repositories/Niam/libdodo/refs/branches', {
        'success': function(data, textStatus, oo) {
            data['values'].forEach(function(a) {
                rv.push(a.name)
            })
            callbacks.forEach(function(a9) {
                a9(rv);
            });
        },
        'error': function(oo, textStatus, errorThrown) {
            e = textStatus+': ' + errorThrown
            e = e.replace('\n', ' ').replace('\r', ' ')
            rv.push(e)
            callbacks.forEach(function(a9) {
                a9(rv);
            });
        }
    });
  }
};


for(var title in title2loader) {
  var getter = title2loader[title];

  Array.from($('td[title="'+title+'"] + td input.qs-editable-input-disabled')).forEach(function(s) {
    var name = $(s).attr('name')
    var den = $(s).attr('data-editor-name')
    var dti = $(s).attr('data-test-id')
    var dic = $(s).attr('data-input-control')
    $(s).replaceWith('<select autocomplete="off" class="qs-editable-input-disabled valid" name="'+name+'" data-test-id="'+dti+'" data-editor-name="'+den+'" data-input-control="'+dic+'" ></select>')
  });

  var callbacks = [];
  Array.from($('td[title="'+title+'"] + td select.qs-editable-input-disabled')).forEach(function(s) {
    $(s).empty();
    $(s).append('<option value="Loading..." selected="selected">Loading...</option>');
    callbacks.push(function(values) {
        $(s).empty()
        values.forEach(function(a) {
          console.log(a)
          $(s).append('<option value="'+a+'">'+a+'</option>')
        });
    });
  });
  getter(callbacks);
}
// [ [test name 1, url for dropdown 1, dropdown value extraction function 1],
//   [test name 2, url for dropdown 2, dropdown value extraction function 2], ... ]
/*
[
  ['ping', 'https://api.bitbucket.org/2.0/repositories/tutorials/tutorials.bitbucket.org/refs/branches'],
  ['cmd /c', 'https://api.bitbucket.org/2.0/repositories/Niam/libdodo/refs/branches']
].forEach(function(title_getter) {
    title = title_getter[0]
    getter = title_getter[1]
    e = $('div:has([value="' + title + '"]) + div input[data-test-id="CustomTestParameter"]')
    id = e.attr('id')
    name = e.attr('name')
    e.replaceWith('<select data-test-id="CustomTestParameter" id="'+id+'" name="'+name+'"></select>')
    load_dropdown('div:has([value="' + title + '"]) + div select[data-test-id="CustomTestParameter"]', getter)
});
*/

return data;