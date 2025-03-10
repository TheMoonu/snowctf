$(function() {
  var simplemde = new SimpleMDE({
    element: document.getElementById("comment-form"),
    autoDownloadFontAwesome: false,
    insertTexts: {
      horizontalRule: ["", "\n\n-----\n\n"],
      image: ["![图片Alt](http://", ")"],
      link: ["[链接描述](http://", ")"],
      table: ["", "\n\n| Column 1 | Column 2 | Column 3 |\n| -------- | -------- | -------- |\n| Text     | Text      | Text     |\n\n"],
    },
    toolbar: [
      {
        name: "bold",
        action: SimpleMDE.toggleBold,
        className: "fa fa-bold",
        title: "粗体",
        "default": true
      },
      {
        name: "italic",
        action: SimpleMDE.toggleItalic,
        className: "fa fa-italic",
        title: "斜体",
        "default": true
      },
      {
        name: "quote",
        action: SimpleMDE.toggleBlockquote,
        className: "fa fa-quote-left",
        title: "引用",
        "default": true
      },
      {
        name: "code",
        action: SimpleMDE.toggleCodeBlock,
        className: "fa fa-code",
        title: "代码"
      },
      {
        name: "link",
        action: SimpleMDE.drawLink,
        className: "fa fa-link",
        title: "插入链接",
        "default": true
      },
      {
        name: "image",
        action: SimpleMDE.drawImage,
        className: "fa fa-picture-o",
        title: "插入图片",
        "default": true
      },
      {
        name: "preview",
        action: SimpleMDE.togglePreview,
        className: "fa fa-eye no-disable",
        title: "预览",
        "default": true
      }
    ],
  });

  $(".comment-body a").attr("target", "_blank");
  
  // 添加以下代码，检查评论内容并控制按钮状态
  // 初始状态下禁用提交按钮
  $("#push-com").prop('disabled', true);
  
  // 监听编辑器内容变化
  simplemde.codemirror.on('change', function() {
    var content = simplemde.value();
    $("#push-com").prop('disabled', !content || content.trim() === '');
  });

  $("<style>#push-com:disabled { opacity: 0.6; cursor: not-allowed; }</style>").appendTo("head");

  $(".editor-statusbar").append("<span class='float-left text-info ml-0 hidden' id='rep-to'></span>");
  $("#editor-footer").append("<button type='button' class='btn btn-danger btn-sm float-right mr-4 f-14 hidden' id='no-rep'>取消回复</button>");

  var emoji_tag = $("#emoji-list img");
  emoji_tag.click(function() {
    var e = $(this).data('emoji');
    simplemde.value(simplemde.value() + e);
  });

  $(".rep-btn").click(function() {
    simplemde.value('');
    var u = $(this).data('repuser');
    var i = $(this).data('repid');
    sessionStorage.setItem('rep_id', i);
    $("#rep-to").text("回复 @" + u).removeClass('hidden');
    $("#no-rep").removeClass('hidden');
    $(".rep-btn").css("color", "#868e96");
    $(this).css("color", "red");
    $('html, body').animate({
      scrollTop: $($.attr(this, 'href')).offset().top - 55
    }, 500);
  });

  $("#no-rep").click(function() {
    simplemde.value('');
    sessionStorage.removeItem('rep_id');
    $("#rep-to").text('').addClass('hidden');
    $("#no-rep").addClass('hidden');
    $(".rep-btn").css("color", "#868e96");
  });

  $("#push-com").click(function() {
    var content = simplemde.value();
    var csrf = $(this).data('csrf');
    var challenge_id = $(this).data('challenge-id');
    var URL = $(this).data('ajax-url');
    var rep_id = sessionStorage.getItem('rep_id');
    var competition_id = $(this).data('competition-id');
    
    // 设置CSRF令牌
    $.ajaxSetup({
      data: {
        'csrfmiddlewaretoken': csrf
      }
    });

    // 提交评论
    $.ajax({
      type: 'post',
      url: URL,
      data: {
        'rep_id': rep_id,
        'content': content,
        'challenge_id': challenge_id,
        'competition_id': competition_id
      },
      dataType: 'json',
      success: function(ret) {
        if (ret.status === 'success') {
          simplemde.value('');
          sessionStorage.removeItem('rep_id');
          if (ret.new_point) {
            sessionStorage.setItem('new_point', ret.new_point);
          }
        }
        window.location.reload();
      },
      error: function() {
        // 发生错误时，重新加载页面以显示Django消息
      window.location.reload();
      }
    });
  });

  if (sessionStorage.getItem('new_point')) {
    var top = $(sessionStorage.getItem('new_point')).offset().top - 100;
    $('body,html').animate({
      scrollTop: top
    }, 200);
    window.location.hash = sessionStorage.getItem('new_point');
    sessionStorage.removeItem('new_point');
  }

  sessionStorage.removeItem('rep_id');
  $(".comment-body a").attr("target", "_blank");
});