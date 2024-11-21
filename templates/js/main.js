let currentDate = '';
let $mealsContainer = $('#meals-container');
let $loading = $('.loading');
let $dateButtons = $('#date-buttons');
let likesData = {};
$(document).ready(function() {
   
    $loading = $('.loading');
    $dateButtons = $('#date-buttons');
    likesData = {};
    // 날짜 버튼 초기화
    function initializeDateButtons() {
        const today = new Date();
        const dates = [];

        for (let i = -3; i <= 3; i++) {
            const date = new Date(today);
            date.setDate(today.getDate() + i);

            // 주말(토,일) 제외
            if (date.getDay() !== 0 && date.getDay() !== 6) {
                dates.push(date.toISOString().split('T')[0]);
            }
        }

        dates.forEach(date => {
            const button = $('<div>')
                .addClass('btn btn-outline-secondary date-btn')
                .attr('data-date', date)
                .text(new Date(date).toLocaleDateString('ko-KR', {
                    month: 'long',
                    day: 'numeric',
                    weekday: 'short'
                }));

            if (date === today.toISOString().split('T')[0]) {
                button.addClass('active');
            }

            $dateButtons.append(button);
        });

        fetchMeals(today.toISOString().split('T')[0]);
    }
    

    
    initializeDateButtons();
    updateVisitCount();
    // 도움말 모달 내용 로드
    $.ajax({
        url: '/help/guide.md',
        method: 'GET',
        success: function(text) {
            // 첫 번째 제목 줄 추출
            const title = text.match(/^#([^\n]*)\n/)[1];
            
            // 첫 번째 제목 줄 제거
            const contentWithoutTitle = text.replace(/^#[^\n]*\n/, '');
            
            // 모달 타이틀 업데이트 
            $('#helpModalLabel').text(title);
            
            // marked.js를 사용하여 마크다운을 HTML로 변환
            $('#helpContent').html(marked.parse(contentWithoutTitle));
        },
        error: function(error) {
            console.error('도움말을 불러오는데 실패했습니다:', error);
        }
    });
});
function updateVisitCount() {
    $.ajax({
        url: '/api/visits/total',
        method: 'GET',
        success: function(response) {
            $('#visit-counter').text(response.count);
        },
        error: function(error) {
            console.error('Error fetching visit count:', error);
        }
    });
}
function fetchMeals(date) {
    $loading.css('display', 'flex');
    currentDate = date;
    $mealsContainer.empty();

    $.ajax({
        url: `/api/meals/${date}`,
        method: 'GET',
        success: function(meals) {
            // 학교명으로 정렬
            meals.sort((a, b) => a.school_name.localeCompare(b.school_name, 'ko'));

            meals.forEach((meal, index) => {
                const cardHtml = createBasicCard(meal, index);
                const $cardCol = $(cardHtml);
                $mealsContainer.append($cardCol);

                // 초기 좋아요 수를 로컬 데이터에 저장
                likesData[meal.school_code] = 0; // 초기값 설정 (필요 시 변경)

                // 리뷰 로드
                loadReview(meal.school_code, date);
            });
        
            
            setInterval(function() {
                
                repositionCards('likes'); 
            }, 30000);
        },
        error: function(xhr, status, error) {
            console.error('Error:', error);
            $mealsContainer.html(`
                <div class="col-12 text-center">
                    <div class="alert alert-danger" role="alert">
                        데이터를 불러오는 중 오류가 발생했습니다.
                    </div>
                </div>
            `);
            $loading.fadeOut();
        },
        complete: function() {
            $loading.fadeOut();
        }
    });
}

function loadReview(schoolCode, date) {
    const card = $(`#school-${schoolCode}`);
    
    const cardCol = card.closest('.card-col');
    const reviewSection = card.find('.review-section');
    const reviewLoading = card.find('.review-loading');


    // const aiIconSvg = `
    // <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width: 20px; height: 22px; margin-right: 0px; vertical-align: -3px;">
    //     <rect x="4" y="6" width="16" height="12" rx="3" fill="none" stroke="#4A90E2" stroke-width="1.5"/>
    //     <text x="12" y="15.5" font-family="Arial" font-size="8" fill="#4A90E2" text-anchor="middle" font-weight="bold">AI</text>
    // </svg>
    // `;
    // AI Review 아이콘 SVG 문자열
    const aiIconSvg = `
    <svg viewBox="0 0 70 24" xmlns="http://www.w3.org/2000/svg" style="width: 60px; height: 22px; margin-right:0px; vertical-align: -4px;">
        <rect x="4" y="4" width="62" height="16" rx="3" fill="none" stroke="#4A90E2" stroke-width="1.5"/>
        <text x="35" y="15.5" font-family="Arial" font-size="10" fill="#4A90E2" text-anchor="middle" font-weight="bold">AI Review</text>
    </svg>`;
    
    reviewLoading.show();
    
    $.ajax({
        url: `/api/review/${date}/${schoolCode}`,
        method: 'GET',
        success: function(review) {
            const schoolName = $(`#school-${schoolCode}>.card-header`).text();
            
            if (review) {
                reviewSection.html(`
                    <div class="review-text">
                        <span class="ai-review-content">
                            ${aiIconSvg}${review.review}
                        </span>
                    </div>
                `);
                
                card.find('.nutri-score').html(createStars('nutri_score',review.nutri_score));
                card.find('.pref-score').html(createStars('pref_score',review.pref_score));

                // 총점 계산 및 저장 (리뷰 점수 합산)
                const totalScore = (review.nutri_score || 0) + (review.pref_score || 0);
                cardCol.data('totalScore', totalScore);

                // 초기 "좋아요" 수를 로컬 데이터에 저장
                likesData[schoolCode] = review.reactions.likes || 0;

                // "좋아요" UI 업데이트
                update_count_ReactionUI(card, review.reactions.likes);
                // 처음 로드 시 총점 순서 재정렬
                repositionCards('score');
            } else {
                reviewSection.html(`
                    <div class="alert alert-warning" role="alert">
                        리뷰가 존재하지 않습니다.
                    </div>
                `);
                cardCol.data('totalScore', 0);
            }

            // 페이지 로드 시 로컬 스토리지 확인 및 버튼 상태 업데이트
            let likedSchools = JSON.parse(localStorage.getItem('likedSchools')) || [];
            if (likedSchools.includes(schoolCode)) {
                card.find('.reaction-btn')
                    .removeClass('text-muted')
                    .addClass('text-primary disabled')
                    .attr('aria-disabled', 'true')
                    .off('click')
                    .css('pointer-events', 'none');
            }
        },
        error: function(xhr, status, error) {
            reviewSection.html(`
                <div class="alert alert-danger" role="alert">
                    리뷰를 불러오는 중 오류가 발생했습니다.
                </div>
            `);
            cardCol.data('totalScore', 0);
        },
        complete: function() {
            reviewLoading.hide();
        }
    });
    
}

function repositionCards(mode='score') {
    const $cardCols = $mealsContainer.children('.card-col').get();

    // 카드 컬럼들을 좋아요 수에 따라 정렬
    if (mode === 'likes') {
        $cardCols.sort(function(a, b) {
            const likesA = parseInt($(a).find('.likes-count').text()) || 0;
            const likesB = parseInt($(b).find('.likes-count').text()) || 0;

            return likesB - likesA; // 내림차순 정렬
        });
    } else {
        // 카드 컬럼들을 총점에 따라 정렬
        $cardCols.sort(function(a, b) {
            const scoreA = $(a).data('totalScore') || 0;
            const scoreB = $(b).data('totalScore') || 0;
            return scoreB - scoreA;
            });
    }

    // 정렬된 순서대로 애니메이션 적용 moveCards()
    // moveCards()
    
        $.each($cardCols, function(index, cardCol) {
            $mealsContainer.append(cardCol);
            $(cardCol).addClass('moving');
            setTimeout(function() {
                $(cardCol).removeClass('moving');
            }, 500); // 애니메이션 시간과 동일하게 설정
        });
  
}


function createStars(mode,score) {
    const fullStars = Math.floor(score);
    const hasHalfStar = score % 1 >= 0.5;
    let starsHtml = '';
    const title={
        'nutri_score'   :'영양학적 평가',
        'pref_score'    :'학생 선호도 측면 평가'
        }
    for (let i = 0; i < 5; i++) {
        if (i < fullStars) {
            starsHtml += '<i class="fas fa-star"></i>';
        } else if (i === fullStars && hasHalfStar) {
            starsHtml += '<i class="fas fa-star-half-alt"></i>';
        } else {
            starsHtml += '<i class="far fa-star"></i>';
        }
    }

    return `
        <div class="stars" title="${title[mode]}">
            ${starsHtml} <small class="text-muted">${score.toFixed(1)}</small>
        </div>
        
    `;
}

function createBasicCard(meal, index) {
    // 한 학교 식단 카드 생성
    return `
        <div class="col-md-6 col-lg-4 mb-4 card-col">
            <div class="card h-100 border border-warning" id="school-${meal.school_code}">
                <div class="card-header py-3 fs-5 text-light" style="background-color: #013b3b;">
                    ${meal.school_name}
                </div>
                <div class="card-body swiper collapse show">
                    <div class="card-text">${meal.lunch_menu}</div>
                    <div class="review-section">
                        <div class="review-loading text-center">
                            <div class="spinner-border spinner-border-sm text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <span class="ms-2">리뷰 생성 중...</span>
                        </div>
                    </div>
                </div>
                <div class="card-footer d-flex justify-content-between align-items-center">
                    <div class="flex-grow-1 review-score text-center d-flex justify-content-center align-items-center gap-2">
                        <div class="nutri-score"></div>
                        <div class="pref-score"></div>
                    </div>
                    <div class="reactions-container text-center">
                        <span class="reaction-btn text-muted cursor-pointer" data-type="like" 
                        data-name="${meal.school_name}"
                        data-school="${meal.school_code}" aria-label="Like ${meal.school_name} School Meal" role="button">
                            <i class="fas fa-thumbs-up"></i>
                        </span>
                        <span class="likes-count">0</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}
// 이벤트 핸들러
$(document).on('click', '.reaction-btn', function(event) {
    event.stopPropagation();
    
    const schoolCode = $(this).data('school');
    const schoolName = $(this).data('name');
    const reactionType = $(this).data('type');
    handleReaction(schoolCode, reactionType, currentDate);
});

$(document).on('click', '.date-btn', function(event) {
    event.stopPropagation();
    $('.date-btn').removeClass('active');
    $(this).addClass('active');
    fetchMeals($(this).data('date'));
});
function handleReaction(schoolCode, reactionType, date) {
    const card = $(`#school-${schoolCode}`);

    if (card.length === 0) {
        console.error(`학교 코드 ${schoolCode}에 해당하는 카드가 존재하지 않습니다.`);
        return;
    }

    
    let schoolLikes = localStorage.getItem(`${currentDate}-${schoolCode}-schoolLikes`) || 0
    
    
    // 좋아요 횟수가 5회 이상인 경우
    if (schoolLikes >= 5) {
        alert('한 학교 급식에 대한 좋아요는 최대 5회까지만 가능합니다.');
        return;
    }

    $.ajax({
        url: `/api/reaction/${date}/${schoolCode}/${reactionType}`,
        method: 'POST',
        success: function(response) {
            // 좋아요 횟수 증가 및 저장
            update_count_ReactionUI(card, response.likes);
            schoolLikes ++;
            localStorage.setItem(`${currentDate}-${schoolCode}-schoolLikes`, schoolLikes);
        },
        error: function(xhr, status, error) {
            alert('반응을 저장하는 중 오류가 발생했습니다.');
        }
    });
}
function update_count_ReactionUI(card, likes) {
    card.find('.likes-count').text(likes);

    if (likes === 0) {
        card.find('.reaction-btn').removeClass('text-primary').addClass('text-muted');
    } else {
        card.find('.reaction-btn').removeClass('text-muted').addClass('text-primary');
    }
}

